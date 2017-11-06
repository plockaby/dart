import logging
import time
import kombu
import kombu.pools
import amqp.exceptions
import socket
import random
import traceback
import cassandra
import cassandra.cluster
from dart.common.killer import GracefulSignalKiller
import dart.common.database
import importlib

# these are the processors that we support
from .processors.active import ActiveConfigurationProcessor
from .processors.pending import PendingConfigurationProcessor
from .processors.probe import ProbeProcessor
from .processors.state import StateProcessor

# import explicitly and specifically like this and NOT as a relative import.
# this is entirely so that we can check if the version number has changed. if
# it changes then we are going to exit so that we can restart ourselves.
import dart.processor


class DartProcessor(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # get configuration from options
        self.verbose = kwargs.get("verbose", False)

        # disable the verbose logging in kombu
        if (not self.verbose):
            logging.getLogger("kombu").setLevel(logging.INFO)
            logging.getLogger("cassandra").setLevel(logging.INFO)

        # this keeps track of whether we've been told to die or not
        self.killer = GracefulSignalKiller()

        # this is when we last checked whether we should die or not. to avoid
        # draining system entropy we won't check more often than every minute.
        self.last_checked = int(time.time())

        # get the connection to cassandra. if we can't get a connection then
        # this will return None and our whole program will not run and that is
        # ok. this is NOT in a for loop like the rabbitmq connection because
        # once cassandra gets a connection it keeps the connection line by
        # itself.
        session = dart.common.database.session(killer=self.killer)
        if (session is None):
            raise RuntimeError("could not get connection to cassandra")

        # these are the processors that we support
        processors = [
            # this handles all active configurations in supervisor
            ActiveConfigurationProcessor(
                session=session,
            ),

            # this handles all pending configurations in supervisor
            PendingConfigurationProcessor(
                session=session,
            ),

            # this handles system information that we've probed
            ProbeProcessor(
                session=session,
            ),

            # this processors state changes from supervisor
            StateProcessor(
                session=session,
            ),
        ]

        # now turn it into a dict for quick lookup when we receive a message
        self.processors = {}
        for processor in processors:
            self.processors[processor.name] = processor

    def run(self):
        finished = False
        while (not finished):
            self.logger.info("starting processing loop")
            try:
                # get a url but randomize it somewhat so that every server
                # isn't connecting to the same instance of rabbitmq.
                configuration = dart.common.configuration.load()
                urls = configuration["rabbitmq"]["urls"]
                connection = kombu.Connection(";".join(random.sample(urls, len(urls))))
                connection.connect()  # force the creation of the connection

                # we listen to several queues
                task_queues = []

                for processor_name in self.processors.keys():
                    # create an exchange to pull things off of. this is a "direct"
                    # exchange which has a routing key.
                    task_exchange = kombu.Exchange(processor_name, type="fanout")

                    # sometimes we want a queue that can only have one consumer at
                    # a time. this is not currently supported by kombu so we have
                    # an override that handles it for us.
                    task_queue_args = [
                        "processor-{}".format(processor_name),
                        task_exchange,
                    ]
                    task_queue_kwargs = {
                        # we don't want stale messages to start things long after
                        # it is relevant. this will clear things out if they stick
                        # around for more than 3600 seconds (1 hour) unprocessed.
                        "message_ttl": 3600,
                    }

                    # create the queue based on what our processor is doing
                    task_queue = kombu.Queue(*task_queue_args, **task_queue_kwargs)

                    # add to the list
                    task_queues.append(task_queue)

                # create the consumer
                consumer = kombu.Consumer(
                    connection,
                    queues=task_queues,
                    callbacks=[self.process_task],
                )
                consumer.consume()

                while (not finished):
                    try:
                        connection.drain_events(timeout=10)
                    except socket.timeout:
                        self.logger.debug("timed out waiting for messages from the message bus")

                    # check to see if we should exit
                    finished = self._should_finish()
            except amqp.exceptions.AccessRefused as e:
                self.logger.warning("queue is already in use: {}".format(repr(e)))
                self.logger.debug(traceback.format_exc())
            except (socket.gaierror, socket.timeout, OSError, TimeoutError, ConnectionError, amqp.exceptions.ConnectionForced) as e:
                self.logger.warning("connection error: {}".format(repr(e)))
                self.logger.debug(traceback.format_exc())
            except Exception as e:
                self.logger.error("unexpected error: {}".format(repr(e)))
                self.logger.error(traceback.format_exc())
            finally:
                # release the connection if possible
                try:
                    connection.release()
                except Exception:
                    pass

                # check again to see if we should exit in here. this way if an
                # error happens on initialization (and we end up in here) we
                # can still get the signal to exit. we only bother to check if
                # we haven't already been told that we're supposed to exit
                if (not finished):
                    finished = self._should_finish()

                # if we're not exiting then we got into here because of an
                # exception and we need to start the loop again. to that end we
                # want to pause for a short spell to see if the reason why we
                # ended up in here cleared up.
                if (not finished):
                    interval = 10
                    self.logger.warn("sleeping for {} seconds before trying again".format(interval))
                    time.sleep(interval)

        # tell everything that we're done
        self.logger.info("exiting")

    def process_task(self, body, message):
        # make sure we got a valid exchange. we are virtually guaranteed that
        # delivery_info is a dict but we aren't guaranteed that it contains
        # anything. thus this should not throw any exceptions.
        exchange = message.delivery_info.get("exchange")
        if (exchange not in self.processors):
            self.logger.error("received message with invalid exchange: {}".format(exchange))
            return

        # make sure it is json that we got
        if (message.content_type != "application/json"):
            self.logger.error("message from '{}' is type '{}' and not application/json".format(exchange, message.content_type))
            return

        try:
            self.processors[exchange].process_task(body, message)
        except cassandra.cluster.NoHostAvailable as e:
            self.logger.warning("{} processor: no cassandra hosts available: {}".format(self.name, repr(e)))
            self.logger.debug(traceback.format_exc())
        except (cassandra.OperationTimedOut, cassandra.RequestExecutionException, cassandra.InvalidRequest) as e:
            self.logger.warning("{} processor: could not execute query on cassandra: {}".format(self.name, repr(e)))
            self.logger.debug(traceback.format_exc())
        except ValueError as e:
            self.logger.warning("{} processor: received unparseable message: {}".format(self.name, body))
            self.logger.debug(traceback.format_exc())
        except Exception as e:
            self.logger.error("{} processor: unexpected error: {}".format(self.name, repr(e)))
            self.logger.error(traceback.format_exc())
        finally:
            # always ack the message, even if we can't process it. that way we
            # don't sit there trying to parse an unparseable message forever.
            # we'll get the data eventually even if we miss a few messages
            message.ack()

    def _should_finish(self):
        if (self.killer.killed()):
            self.logger.info("exiting because we were killed")
            return True

        if (self._has_version_changed()):
            self.logger.info("exiting because of version change")
            return True

        if (self.last_checked + 60 < int(time.time())):
            if (random.randint(1, 60 * 24 * 3) == 1):
                self.logger.info("randomly exiting")
                return True
            else:
                self.last_checked = int(time.time())

        return False

    def _has_version_changed(self):
        try:
            old_version = dart.processor.__version__
            importlib.reload(dart.processor)
            new_version = dart.processor.__version__

            if (old_version != new_version):
                self.logger.info("new version {} is not the same as old version {}".format(new_version, old_version))
                return True
        except Exception as e:
            pass

        return False
