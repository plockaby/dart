from . import BaseHandler
import dart.common.event
import logging
import traceback
from threading import Thread
import kombu
import kombu.pools
import amqp.exceptions
import socket
import random
import time


class QueueHandler(BaseHandler):
    def __init__(self, queue, **kwargs):
        super().__init__(**kwargs)

        # disable the verbose logging in kombu
        logging.getLogger("kombu").setLevel(logging.INFO)

        # this is the queue that we should read off of
        self.queue = queue

    @property
    def name(self):
        return "queue"

    def start(self):
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # we only have one worker so we just tell the queue once that we have
        # nothing left and then wait for it to be done.
        self.queue.put(None)
        self.queue.join()

        # then join the thread that started the whole mess
        self.thread.join()

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle since we can't handle anything
        pass

    # this is the only method that is threaded. everything else is run in the
    # main program thread. this method should also not call out to any other
    # methods that aren't thread safe.
    def _run(self):
        # generate the url out here so that it is randomized in the same way.
        # we randomize it so that all clients aren't connecting to the same
        # instance every time. but we want to randomize it once so that we
        # don't create a new pool on every connection failure.
        configuration = dart.common.configuration.load()
        urls = configuration["rabbitmq"]["urls"]
        url = ";".join(random.sample(urls, len(urls)))

        finished = False
        clear_error = True
        while (not finished):
            try:
                # reload the configuration to get the most recent username and
                # password before connecting to the message bus. the url itself
                # is randomized once at the top of this method.
                configuration = dart.common.configuration.load()
                username = configuration["rabbitmq"]["username"]
                password = configuration["rabbitmq"]["password"]

                # get a connection object to the message bus
                connection = kombu.Connection(url.format(username=username, password=password))

                # loop forever -- after getting a message off of the queue on
                # which we are listening, we transfer it to the message bus.
                # after putting it onto the message bus we wait for more.
                while (True):
                    item = None
                    try:
                        # this will block while waiting for messages to appear
                        # on the local thread queue. we immediately acknowledge
                        # it off of the local thread queue so that if there is
                        # an exception then we can put it back on the queue.
                        item = self.queue.get()
                        self.queue.task_done()

                        # if "None" is put on the queue then we are to stop
                        # listening to the queue. this happens when someone
                        # calls the ".stop" method to this class.
                        if (item is None):
                            self.logger.debug("{} handler cleaning up before exit".format(self.name))
                            finished = True
                            break

                        # create an exchange based on the item we were given.
                        # we only use "fanout" exchanges. that means that
                        # anything published to this exchange will be sent to
                        # ALL bound queues. this is UNLINKE a "direct" exchange
                        # where the message would have a routing key that would
                        # direct the message to one or more particular queues.
                        exchange_name = item.get("exchange")
                        if (exchange_name is None):
                            raise ValueError("missing exchange from item to enqueue")
                        exchange = kombu.Exchange(exchange_name, type="fanout")

                        # this is what we're going to enqueue
                        payload = item.get("payload")
                        if (payload is None):
                            raise ValueError("missing payload from item to enqueue")

                        # now send it to the message bus
                        with kombu.pools.producers[connection].acquire(block=True) as producer:
                            producer.publish(
                                payload,
                                exchange=exchange,
                                declare=[exchange],
                                retry=True,
                            )

                        # now clear any error events, if necessary. because the
                        # volume of this queue is high, we only want to clear
                        # events when we have something to clear.
                        if (clear_error):
                            dart.common.event.send(
                                component="dart:agent:{}".format(self.name),
                                severity=6,
                                subject="clear",
                            )
                            clear_error = False
                    except Exception as e:
                        # if we have an exception we're going to try to put it
                        # on the queue later. then we re-raise the exception so
                        # that we can try to connect to the message bus again.
                        # this could potentially raise an infinite loop if the
                        # exception was caused by the item itself. however, if
                        # keep this try block minimal then the exception most
                        # likely was caused by a connection issue and we want
                        # try again in that event.
                        self.queue.put(item)
                        raise e
            except (socket.gaierror, socket.timeout, TimeoutError, ConnectionError, amqp.exceptions.ConnectionForced, amqp.exceptions.AccessRefused, amqp.exceptions.NotAllowed) as e:
                subject = "queue listener connection error: {}".format(repr(e))
                message = traceback.format_exc()
                self.logger.warning(subject)
                self.logger.warning(message)

                # these errors are transient connecting to the message bus. as
                # soon as something is successfully published to the message
                # bus this event will clear.
                dart.common.event.send(
                    component="dart:agent:{}".format(self.name),
                    severity=3,
                    subject=subject,
                    message=message,
                )

                # this error should clear be cleared when we are able to
                # successfully process something.
                clear_error = True
            except Exception as e:
                subject = "unexpected error in queue listener: {}".format(repr(e))
                message = traceback.format_exc()
                self.logger.error(subject)
                self.logger.error(message)

                # problems that we didn't expect should create non-escalating
                # incidents. this event will not automatically clear.
                dart.common.event.send(
                    component="dart:agent:{}:error".format(self.name),
                    severity=2,
                    subject=subject,
                    message=message,
                )
            finally:
                if (not finished):
                    interval = 10
                    self.logger.warning("{} handler sleeping for {} seconds before trying again".format(self.name, interval))
                    time.sleep(interval)

        # tell everything that we're done
        self.logger.info("{} handler exiting".format(self.name))
