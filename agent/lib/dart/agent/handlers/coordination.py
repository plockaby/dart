from . import BaseHandler
import dart.common.event
import dart.common.configuration
from dart.common.killer import GracefulEventKiller
from dart.common.supervisor import SupervisorClient
import logging
import traceback
from threading import Thread
import xmlrpc.client
import kombu
import kombu.pools
import amqp.exceptions
import socket
import random
import time


# disable the verbose logging in kombu
logging.getLogger("kombu").setLevel(logging.INFO)


class CoordinationHandler(BaseHandler):
    def __init__(self, supervisor_server_url, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # this is how we connect to supervisor
        self.supervisor_server_url = supervisor_server_url

        # we can set these to force a reread or a rewrite
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this will be triggered when it is time to die
        self.killer = GracefulEventKiller()

    @property
    def name(self):
        return "coordination"

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle since we can't handle anything
        pass

    def start(self):
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the thread to stop using a thread safe mechanism
        self.killer.kill()

        # then wait for our thread to be finished
        self.thread.join()

    def _run(self):
        try:
            finished = False
            clear_error = True
            while (not finished and not self.killer.killed()):
                try:
                    # get a url but randomize it somewhat so that every server
                    # isn't connecting to the same instance of rabbitmq.
                    configuration = dart.common.configuration.load()
                    urls = configuration["rabbitmq"]["urls"]
                    connection = kombu.Connection(";".join(random.sample(urls, len(urls))))

                    # this is a "direct" exchange which has a routing key. the
                    # routing key should be our fully qualified domain name soi
                    # that we only try to run things over which we have control.
                    task_exchange = kombu.Exchange("coordinator", type="direct")

                    # a queue that only listens for things directed toward us.
                    task_queue = kombu.Queue(
                        # using an empty name for the queue gets us a unique name.
                        # this prevents ResourceLocked exceptions. the exchange is
                        # built such that all queues get all messages so we should
                        # always be getting the messages regardless of any phantom
                        # queues that may stick around on connection problems.
                        "",

                        # but this is where our messages come from and they are
                        # addressed to us with the routing key.
                        task_exchange,
                        routing_key=self.fqdn,

                        # we want the queue to go away when we're done with it.
                        auto_delete=True,

                        # this queue should only allow one consumer at a time.
                        # because the queue is named at random by the message bus
                        # we no longer run into errors regarding locked resources so
                        # this is a safe action.
                        exclusive=True,

                        # we don't want stale messages to start things long after
                        # it is relevant. this will clear things out if they stick
                        # around for more than 90 seconds unprocessed.
                        message_ttl=90,
                    )

                    # create the consumer
                    consumer = kombu.Consumer(connection, queues=task_queue, callbacks=[self._process_task])
                    consumer.consume()

                    # keep trying to drain events until we are told to exit
                    while (not self.killer.killed()):
                        try:
                            # wait one second for data before going back to see
                            # if we are supposed to exit.
                            connection.drain_events(timeout=1)
                        except socket.timeout:
                            self.logger.debug("{} handler timed out waiting for messages from the message bus".format(self.name))

                        # now clear any error events if necessary. because the
                        # volume of this event handler could be high, we only want
                        # to clear events when we have something to clear.
                        if (clear_error):
                            dart.common.event.send(
                                component="dart:agent:{}".format(self.name),
                                severity=6,
                                subject="clear",
                            )
                            clear_error = False
                    else:
                        finished = True
                except (socket.gaierror, socket.timeout, OSError, TimeoutError, ConnectionError, amqp.exceptions.ConnectionForced) as e:
                    subject = "{} handler connection error: {}".format(self.name, repr(e))
                    message = traceback.format_exc()
                    self.logger.warning(subject)
                    self.logger.warning(message)

                    # this is a connection error that we want to know about but we
                    # don't want an incident for it. this error will clear
                    # automatically the next time we successfully listen to the
                    # queue.
                    dart.common.event.send(
                        component="dart:agent:{}".format(self.name),
                        severity=3,
                        subject=subject,
                        message=message,
                    )

                    # mark that we have an event to clear otherwise the clear event
                    # won't be sent.
                    clear_error = True
                except Exception as e:
                    subject = "{} handler unexpected error: {}".format(self.name, repr(e))
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
                    try:
                        # release the connection if possible
                        connection.release()
                    except Exception:
                        pass

                    # we might not be able to check that we were killed in the
                    # loop above if we hit an exception while connecting to
                    # rabbitmq so we'll check again here.
                    if (not finished and not self.killer.killed()):
                        interval = 10
                        self.logger.warn("{} handler sleeping for {} seconds before trying again".format(self.name, interval))
                        time.sleep(interval)
        except Exception as e:
            subject = "{} handler unexpected error launching agent: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # we should only end up in here if something went really terribly
            # wrong setting up the handler. we should raise a high severity to
            # get dart restarted.
            dart.common.event.send(
                component="dart:agent:{}:error".format(self.name),
                severity=1,
                subject=subject,
                message=message,
            )

        # tell everything that we're done
        self.logger.info("{} handler exiting".format(self.name))

    def _process_task(self, body, msg):
        # methods we implement on the supervisor xml-rpc api:
        # - startProcess(name, wait=False)  <- wait is True by default, we want false
        # - stopProcess(name, wait=False)  <- wait is True by default, we want false
        # - addProcessGroup(name)
        # - removeProcessGroup(name)

        # these are faux commands that we support
        # - restartProcess(name)  <- calls stop/start
        # - updateProcessGroup(name)  <- calls stop/add/remove

        # format is expected to look kind of like this:
        # {
        #     action="start/stop/add/remove/restart/update",  <- one of the commands above
        #     process="name",                                 <- the process against which to run the command
        # }

        # convert the body into json
        try:
            self.logger.debug("{} handler received: {}".format(self.name, body))

            # make sure it is json that we got
            if (msg.content_type != "application/json"):
                raise ValueError("{} message is type {} and not application/json".format(self.name, msg.content_type))

            # make sure we have a valid action
            action = body.get("action")
            if (action is None or action.strip() == ""):
                raise ValueError("missing action")
            if (action not in ["start", "stop", "add", "remove", "restart", "update", "reread", "rewrite"]):
                raise ValueError("invalid action")

            if (action in ["reread", "rewrite"]):
                if (action == "reread"):
                    self.logger.info("{} handler triggering a reread".format(self.name))
                    self.reread_trigger.set()
                if (action == "rewrite"):
                    self.logger.info("{} handler triggering a rewrite".format(self.name))
                    self.rewrite_trigger.set()
            else:
                # this is the thing we're going to do it to
                process = body.get("process")
                if (process is None or process.strip() == ""):
                    raise ValueError("missing process")

                if (action == "start"):
                    self.__start_process(process)
                if (action == "stop"):
                    self.__stop_process(process)
                if (action == "restart"):
                    self.__restart_process(process)
                if (action == "add"):
                    self.__add_process(process)
                if (action == "remove"):
                    self.__remove_process(process)
                if (action == "update"):
                    self.__update_process(process)

                # after all commands we want to reread the system state
                self.logger.info("{} handler triggering a reread".format(self.name))
                self.reread_trigger.set()
        except ValueError as e:
            subject = "{} handler received unparseable message: {}".format(self.name, body)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)

            # let the people know something dumb happened but it's not that
            # important to fix. this event will not clear automatically.
            dart.common.event.send(
                component="dart:agent:{}:task".format(self.name),
                severity=4,
                subject=subject,
                message=message,
            )
        except Exception as e:
            subject = "{} handler unexpected error: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # this is a problem that we didn't expect so create an incident.
            # this event will not clear automatically.
            dart.common.event.send(
                component="dart:agent:{}:task:error".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )
        finally:
            # always ack the message, even if we can't process it. that way we
            # don't sit there trying to parse an unparseable message forever.
            msg.ack()

    def __start_process(self, process, wait=False):
        self.logger.info("{} handler starting process: {}".format(self.name, process))
        try:
            client = SupervisorClient(self.supervisor_server_url)
            client.connection.supervisor.startProcess(process, wait)
        except xmlrpc.client.Fault as e:
            self.logger.warning("{} handler could not start process {}: {}".format(self.name, process, e.faultString))

    def __stop_process(self, process, wait=False):
        self.logger.info("{} handler stopping process: {}".format(self.name, process))
        try:
            client = SupervisorClient(self.supervisor_server_url)
            client.connection.supervisor.stopProcess(process, wait)
        except xmlrpc.client.Fault as e:
            self.logger.warning("{} handler could not stop process {}: {}".format(self.name, process, e.faultString))

    def __add_process(self, process):
        self.logger.info("{} handler adding process: {}".format(self.name, process))
        try:
            client = SupervisorClient(self.supervisor_server_url)
            client.connection.supervisor.addProcessGroup(process)
        except xmlrpc.client.Fault as e:
            self.logger.warning("{} handler could not add process {}: {}".format(self.name, process, e.faultString))

    def __remove_process(self, process):
        self.logger.info("{} handler removing process: {}".format(self.name, process))
        try:
            client = SupervisorClient(self.supervisor_server_url)
            client.connection.supervisor.removeProcessGroup(process)
        except xmlrpc.client.Fault as e:
            self.logger.warning("{} handler could not remove process {}: {}".format(self.name, process, e.faultString))

    def __restart_process(self, process):
        self.__stop_process(process, wait=True)
        self.__start_process(process)

    def __update_process(self, process):
        # we can't remove a process that is running
        self.__stop_process(process, wait=True)

        # then actually remove it
        self.__remove_process(process)

        # if a process is configured to automatically start then it will
        self.__add_process(process)
