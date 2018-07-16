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
from statsd import StatsClient
from dart.common.killer import GracefulSignalKiller
import dart.common.database

# these are the processors that we support
from .processors.active import ActiveConfigurationProcessor
from .processors.pending import PendingConfigurationProcessor
from .processors.probe import ProbeProcessor
from .processors.state import StateProcessor


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

        # get the connection to cassandra. if we can't get a connection then
        # this will return None and our whole program will not run and that is
        # ok. this is NOT in a for loop like the rabbitmq connection because
        # once cassandra gets a connection it keeps the connection line by
        # itself.
        self.session = dart.common.database.session(killer=self.killer)
        if (self.session is None):
            raise RuntimeError("could not get connection to cassandra")

        # keep track of how long various things take
        configuration = dart.common.configuration.load()
        if (not configuration.get("statsd", {}).get("disabled", True)):
            self.statsd = StatsClient(
                host=configuration.get("statsd", {}).get("host", "localhost"),
                port=configuration.get("statsd", {}).get("port", 8125),
                prefix="dart.processor",
                maxudpsize=1500,
            )
        else:
            self.statsd = None

        # these are the processors that we support
        processors = [
            # this handles all active configurations in supervisor
            ActiveConfigurationProcessor(
                session=self.session,
            ),

            # this handles all pending configurations in supervisor
            PendingConfigurationProcessor(
                session=self.session,
            ),

            # this handles system information that we've probed
            ProbeProcessor(
                session=self.session,
            ),

            # this processors state changes from supervisor
            StateProcessor(
                session=self.session,
            ),
        ]

        # now turn it into a dict for quick lookup when we receive a message
        self.processors = {}
        for processor in processors:
            self.processors[processor.name] = processor

    def __del__(self):
        try:
            # this will wait for all async queries to finish
            self.session.shutdown()
        except Exception:
            pass

    def run(self):
        # generate the url out here so that it is randomized in the same way.
        # we randomize it so that all clients aren't connecting to the same
        # instance every time. but we want to randomize it once so that we
        # don't create a new pool on every connection failure.
        configuration = dart.common.configuration.load()
        urls = configuration["rabbitmq"]["urls"]
        url = ";".join(random.sample(urls, len(urls)))

        finished = False
        while (not finished):
            self.logger.info("starting processing loop")
            try:
                # reload the configuration to get the most recent username and
                # password before connecting to the message bus. the url itself
                # is randomized once at the top of this method.
                configuration = dart.common.configuration.load()
                username = configuration["rabbitmq"]["username"]
                password = configuration["rabbitmq"]["password"]

                # get a connection object to the message bus
                connection = kombu.Connection(url.format(username=username, password=password))

                # we listen to several queues
                task_queues = []

                for processor_name in self.processors.keys():
                    task_queues.append(kombu.Queue(
                        # connect to a queue that is named after what it is
                        # processing. this will create the queue if it does
                        # not exist.
                        "processor-{}".format(processor_name),

                        # connect the queue to the exchange that is named after
                        # what we are processing. this will create the exchange
                        # if it does not exist.
                        kombu.Exchange(processor_name, type="fanout"),

                        # we don't want stale messages to start things long
                        # after it is relevant. this will clear things out if
                        # they stick around for more than 3600 seconds (1 hour)
                        # unprocessed.
                        message_ttl=3600,
                    ))

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
                        pass

                    # check to see if we should exit
                    finished = self._should_finish()
            except (socket.gaierror, socket.timeout, OSError, TimeoutError, ConnectionError, amqp.exceptions.ConnectionError, amqp.exceptions.ChannelError) as e:
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
        self.logger.info("gracefully exiting")
        return 0

    def process_task(self, body, message):
        try:
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

            if (self.statsd):
                self.statsd.incr("{}.messages".format(exchange))
                with self.statsd.timer("{}.process.task".format(exchange)):
                    self.processors[exchange].process_task(body, message)
            else:
                self.processors[exchange].process_task(body, message)
        except cassandra.cluster.NoHostAvailable as e:
            self.logger.warning("{} processor: no cassandra hosts available: {}".format(exchange, repr(e)))
            self.logger.debug(traceback.format_exc())
        except (cassandra.OperationTimedOut, cassandra.RequestExecutionException, cassandra.InvalidRequest) as e:
            self.logger.warning("{} processor: could not execute query on cassandra: {}".format(exchange, repr(e)))
            self.logger.debug(traceback.format_exc())
        except ValueError as e:
            self.logger.warning("{} processor: received unparseable message: {}".format(exchange, body))
            self.logger.debug(traceback.format_exc())
        except Exception as e:
            self.logger.error("{} processor: unexpected error: {}".format(exchange, repr(e)))
            self.logger.error(traceback.format_exc())
        finally:
            # always ack the message, even if we can't process it. that way we
            # don't sit there trying to parse an unparseable message forever.
            # we'll get the data eventually even if we miss a few messages
            try:
                message.ack()
            except Exception:
                pass

    def _should_finish(self):
        if (self.killer.killed()):
            self.logger.info("exiting because we were killed")
            return True

        return False
