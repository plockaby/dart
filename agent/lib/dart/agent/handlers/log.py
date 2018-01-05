from . import BaseHandler
import dart.common.event
from dart.common.killer import GracefulEventKiller
from threading import Thread, RLock, Event
from queue import Queue
import traceback
import time
import copy
import re


class LogHandler(BaseHandler):
    def __init__(self, configuration_path, configuration_file, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

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
        return "log"

    def start(self):
        # try to load our configuration file
        self.logger.debug("{} handler reading configuration".format(self.name))
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

        # start the log processor
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
        return event_type.startswith("PROCESS_LOG_")

    def handle(self, event_type, event, data):
        self.processor.put({"event": event, "data": data})

    # this method runs in a thread
    def _run_configuration_loader(self):
        while (not self.killer.killed()):
            if (self.reread_trigger.wait(timeout=1)):
                try:
                    with self.configuration_lock:
                        self.logger.debug("{} handler rereading configuration".format(self.name))

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
        self.logger.debug("{} handler configuration loader exiting".format(self.name))

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
                    self.logger.debug("{} handler queue listener cleaning up before exit".format(self.name))
                    finished = True
                else:
                    self._check(item["event"], item["data"])
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

    def _check(self, event, data):
        # events look like this:
        #
        #   {
        #       'pid': '27532',
        #       'groupname': 'gaggregator-publisher',
        #       'channel': 'stdout',
        #       'processname': 'gaggregator-publisher'
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

            # process each log line through the monitoring configuration
            process = event["processname"]
            stream = event["channel"]

            # make sure this process is monitored for this stream
            if (process in self.configuration_copy["log"][stream]):
                # there may be multiple regexes for each process/stream
                # combination. run each line against each regex. we will also
                # validate the regular expression and raise an event if the
                # regex is invalid
                lines = list(filter(len, data.split("\n")))
                for line in lines:
                    for monitor in self.configuration_copy["log"][stream][process]:
                        component = "dart:monitor:{}:{}".format(stream, process)
                        if (monitor["name"]):
                            component = "{}:{}".format(component, monitor["name"])

                        try:
                            regex = re.compile(monitor["regex"])
                        except re.error as e:
                            self.logger.error("{} handler invalid regular expression '{}' for {} on {}".format(self.name, monitor["regex"], process, stream))
                            dart.common.event.send(
                                component=component,
                                severity=2,
                                subject="invalid regular expression '{}'".format(monitor["regex"]),
                                message=repr(e),
                            )

                            # can't do anything else with this monitor
                            break

                        if (regex.search(line)):
                            self.logger.debug("{} handler matched '{}' for {} on {}".format(self.name, monitor["regex"], process, stream))

                            # some regexes don't have severities set. in that
                            # case we do not create any events. this typically
                            # happens in combination with "stop".
                            if (monitor["severity"]):
                                dart.common.event.send(
                                    component=component,
                                    severity=monitor["severity"],
                                    contact=monitor["contact"],
                                    subject=line,
                                    message=data,
                                )

                            # if the monitor matched this line and it has the
                            # "stop" configuration set then we break out of the
                            # monitors loop and then process the next line.
                            if (monitor["stop"]):
                                self.logger.debug("{} handler stopping log processing for {} on {} because of stop rule".format(self.name, process, stream))
                                break
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
