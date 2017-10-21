import logging
import kombu
import kombu.pools
import traceback
import socket
import random
import importlib
import time
import amqp.exceptions
import dart.common.configuration
from dart.common.killer import GracefulSignalKiller
import dart.common.database

# import explicitly and specifically like this and NOT as a relative import.
# this is entirely so that we can check if the version number has changed. if
# it changes then we are going to exit so that we can restart ourselves.
import dart.processor


# disable the verbose logging in kombu
logging.getLogger("kombu").setLevel(logging.INFO)


class BaseProcessor(object):
    def __init__(self, exchange_name, **kwargs):
        # everything needs a logger!
        self.logger = logging.getLogger(__name__)

        # get configuration from options
        self.verbose = kwargs.get("verbose", False)

        # this keeps track of whether we've been told to die or not
        self.killer = GracefulSignalKiller()

        # this is the name of the exchange we'll connect to and part of the
        # name of the queue we will create
        self.exchange_name = exchange_name

        # this is our cassandra connection. it gets made when we start running
        self.session = None

        # who we are for keepalive purposes
        self.fqdn = socket.getfqdn()

        # this is when we last checked whether we should die or not. to avoid
        # draining system entropy we won't check more often than every minute.
        self.last_checked = int(time.time())

        # get the connection to cassandra. if we can't get a connection then
        # this will return None and our whole program will not run and that is
        # ok. this is NOT in a for loop like the rabbitmq connection because
        # once cassandra gets a connection it keeps the connection line by
        # itself.
        self.session = dart.common.database.session(killer=self.killer)
        if (self.session is None):
            raise RuntimeError("could not get connection to cassandra")

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

                # create an exchange to pull things off of. this is a "direct"
                # exchange which has a routing key.
                task_exchange = kombu.Exchange(self.exchange_name, type="fanout")

                # sometimes we want a queue that can only have one consumer at
                # a time. this is not currently supported by kombu so we have
                # an override that handles it for us.
                task_queue_args = [
                    "processor-{}".format(self.exchange_name),
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

                # create the consumer
                consumer = kombu.Consumer(
                    connection,
                    queues=task_queue,
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

    @property
    def name(self):
        raise NotImplementedError("property must be implemented in subclass")

    def process_task(self, body, message):
        raise NotImplementedError("must be implemented in subclass")

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
