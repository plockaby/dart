from . import BaseHandler
import dart.common.event
from dart.common.supervisor import SupervisorClient
from dart.common.killer import GracefulEventKiller
from threading import Thread, RLock, Event
from queue import Queue
import xmlrpc.client
import traceback
import time
import copy


class StateHandler(BaseHandler):
    def __init__(self, queue, supervisor_server_url, configuration_path, configuration_file, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # this is the queue that will put things on the message bus
        self.queue = queue

        # this is how we connect to supervisor
        self.supervisor_server_url = supervisor_server_url

        # this is where we will try to read configurations
        self.configuration_path = configuration_path
        self.configuration_file = configuration_file

        # used to trigger configuration file rewrites
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

        # this locks the configuration data store so that it can be used be
        # used by the multiple threads
        self.configuration_lock = RLock()

        # this gets triggered when we've changed the configuration
        self.configuration_changed = Event()

        # this is the configuration that we've loaded
        self.configuration = None

        # this is a copy of the configuration that is local to the processing
        # thread. this copy should NEVER be used outside of the processing
        # thread. by keeping a copy we are able to avoid doing a deep copy
        # for every single event that we get and instead only do a deep copy
        # when the configuration changes.
        self.configuration_copy = None

        # things that we put into here will be processed in our thread
        self.processor = Queue()

        # we start a couple threads
        self.threads = []

    @property
    def name(self):
        return "state"

    def start(self):
        # try to load our configuration file
        self.logger.info("{} handler reading configuration".format(self.name))
        with self.configuration_lock:
            while (self.configuration is None):
                self.configuration = self._load_configuration(self.configuration_path, self.configuration_file)
                self.configuration_changed.set()

                # if our monitoring configuration is still empty then we will
                # wait for them to become available.
                if (self.configuration is None):
                    self.logger.warning("{} handler sleeping before trying to read configurations again".format(self.name))
                    time.sleep(1)

        # start our configuration listener
        thread = Thread(target=self._run_configuration_loader)
        thread.start()
        self.threads.append(thread)

        # start the queue processor
        thread = Thread(target=self._run)
        thread.start()
        self.threads.append(thread)

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the thread to stop using a thread safe mechanism
        self.killer.kill()

        # tell our queue to stop. the queue MUST stop before we can join our
        # threads or else we will have a condition where the thread won't stop
        # until the queue stops and the queue can't be told to stop.
        self.processor.put(None)
        self.processor.join()

        # then wait for our thread to be finished
        for thread in self.threads:
            thread.join()

    def can_handle(self, event_type):
        return event_type.startswith("PROCESS_STATE_")

    def handle(self, event_type, event, data):
        self.processor.put({"type": event_type, "event": event})

    # this method runs in a thread
    def _run_configuration_loader(self):
        while (not self.killer.killed()):
            if (self.reread_trigger.wait(timeout=1)):
                try:
                    with self.configuration_lock:
                        self.logger.info("{} handler rereading configuration".format(self.name))

                        # don't just blindly load the configuration. ensure
                        # that we were able to actually load the file before
                        # replacing what we have right now.
                        configuration = self._load_configuration(self.configuration_path, self.configuration_file)
                        if (configuration is not None):
                            self.configuration = configuration
                            self.configuration_changed.set()
                        else:
                            self.logger.warning("{} handler not replacing a good configuration with a bad configuration".format(self.name))
                finally:
                    # this clears the trigger so that it can be set again
                    self.reread_trigger.clear()

        # note that this thread is finished
        self.logger.info("{} handler configuration loader exiting".format(self.name))

    # this method runs in a thread
    def _run(self):
        finished = False
        while (not finished):
            item = None
            try:
                # this will block while waiting for messages to appear on the
                # local thread queue. we immediately acknowledge it off of the
                # local thread queue so that we don't get caught up processing
                # things that we can't process.
                item = self.processor.get()
                self.processor.task_done()

                # if "None" is put on the queue then we are to stop listening
                # to the queue. this happens when someone calls the ".stop"
                # method on the class.
                if (item is None):
                    self.logger.info("{} handler queue listener cleaning up before exit".format(self.name))
                    finished = True
                else:
                    self._check(item["type"], item["event"])
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

        self.logger.info("{} handler queue listener exiting".format(self.name))

    def _check(self, event_type, event):
        # events look like this:
        #
        #   {
        #       'pid': '22455',
        #       'expected': '1',
        #       'groupname': 'unison-bowser-shared',
        #       'from_state': 'RUNNING',
        #       'processname': 'unison-bowser-shared'
        #   }
        #
        # when we query for process info we get this:
        #
        #   {
        #       'logfile': '/data/logs/supervisor/unison-bowser-shared.log',
        #       'group': 'unison-bowser-shared',
        #       'stderr_logfile': '',
        #       'spawnerr': '',
        #       'state': 100,
        #       'description': 'Aug 10 05:03 PM',
        #       'exitstatus': 0,
        #       'pid': 0,
        #       'name': 'unison-bowser-shared',
        #       'now': 1502409784,
        #       'stop': 1502409784,
        #       'statename': 'EXITED',
        #       'start': 1502409781,
        #       'stdout_logfile': '/data/logs/supervisor/unison-bowser-shared.log'
        #   }
        #
        try:
            # copy the configuration if it has changed
            if (self.configuration_changed.wait(timeout=0)):
                with self.configuration_lock:
                    try:
                        self.configuration_copy = copy.deepcopy(self.configuration)
                    finally:
                        self.configuration_changed.clear()

            # get the process information from supervisor
            client = SupervisorClient(self.supervisor_server_url)
            state = client.connection.supervisor.getProcessInfo(event["processname"])

            # send the state message to the message bus
            self.logger.info("recording state change on {} to {}".format(event["processname"], event_type))
            self.queue.put(dict(
                exchange="state",
                payload=dict(
                    fqdn=self.fqdn,
                    state=state,
                )
            ))

            # process the state message through the monitoring configuration
            process = state["name"]

            if (process in self.configuration_copy["state"]):
                configuration = self.configuration_copy["state"][process]

                if (state["statename"] == "RUNNING"):
                    # if the process is successfully running then clear any
                    # state alerts for it.
                    self.logger.info("{} handler clearing state event for {} because it is now RUNNING".format(self.name, process))
                    dart.common.event.send(
                        component="dart:monitor:state:{}".format(process),
                        severity=6,
                        subject="clear",
                    )
                else:
                    # if this process is being state monitored and it has gone
                    # into one of these error states then raise an error.
                    if (state["statename"] in ["UNKNOWN", "FATAL", "BACKOFF"]):
                        self.logger.info("{} handler raising state event for {} because it has gone into state {}".format(self.name, process, state["statename"]))
                        dart.common.event.send(
                            component="dart:monitor:state:{}".format(process),
                            severity=configuration["severity"],
                            contact=configuration["contact"],
                            subject="{} entered the state {}".format(process, state["statename"]),
                            message=state["spawnerr"],
                        )

                    # if this process is being state monitored and it returned
                    # an error when it exited then raise an error.
                    elif (state["spawnerr"]):
                        self.logger.info("{} handler raising state event for {} because it exited with an error".format(self.name, process))
                        dart.common.event.send(
                            component="dart:monitor:state:{}".format(process),
                            severity=configuration["severity"],
                            contact=configuration["contact"],
                            subject="{} exited with an error".format(process),
                            message=state["spawnerr"],
                        )

            if (process in self.configuration_copy["daemon"]):
                configuration = self.configuration_copy["daemon"][process]

                if (state["statename"] == "RUNNING"):
                    # if the process is successfully running then clear any
                    # daemon alerts for it.
                    self.logger.info("{} handler clearing daemon event for {} because it is now RUNNING".format(self.name, process))
                    dart.common.event.send(
                        component="dart:monitor:daemon:{}".format(process),
                        severity=6,
                        subject="clear",
                    )
                else:
                    self.logger.info("{} handler raising daemon event for {} because it is in state {} when it is supposed to be in state RUNNING".format(self.name, process, state["statename"]))
                    dart.common.event.send(
                        component="dart:monitor:daemon:{}".format(process),
                        severity=configuration["severity"],
                        contact=configuration["contact"],
                        subject="{} is in state {} when it is supposed to be in state RUNNING".format(process, state["statename"]),
                    )
        except xmlrpc.client.Fault as e:
            # don't want to raise any alarms about this one
            subject = "{} handler could not get process state from supervisor: {}".format(self.name, e.faultString)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)
        except Exception as e:
            subject = "{} handler unexpected error: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # problems that we didn't expect should create
            # non-escalating incidents. this event will not clear
            # automatically.
            dart.common.event.send(
                component="dart:agent:{}:error".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )
