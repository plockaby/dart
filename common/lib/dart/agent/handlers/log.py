"""
This handler listens for log events and if they match a monitoring
configuration creates an event.
"""

from . import BaseHandler
from ..settings import SettingsManager
from ..configurations import ConfigurationsManager
from dart.common.killer import GracefulEventKiller
from threading import Thread
from queue import Queue
import traceback
import re


class LogHandler(BaseHandler):
    def __init__(self, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # get program settings into ourselves
        self.settings = SettingsManager().get("monitor", {})
        self.configurations = ConfigurationsManager()

        # used to trigger configuration file rewrites
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

        # all logs are received and put on a queue for processing. this is
        # that queue. "processing" means running it through regular expressions
        # and sending the result to dart.
        self.processor = Queue()

    @property
    def name(self):
        return "log"

    def start(self):
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the thread to stop using a thread safe mechanism
        self.killer.kill()

        # tell our queue to stop. the queue MUST stop before we can join our
        # threads or else we will have a condition where the thread won't stop
        # until the queue stops and the queue can't be told to stop.
        self.processor.put(None)
        self.processor.join()

        # then wait for the processing thread to finish
        self.thread.join()

    def can_handle(self, event_type):
        return event_type.startswith("PROCESS_LOG_")

    def handle(self, event_type, event, data):
        self.processor.put({"event": event, "data": data})

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
                subject = "unexpected error in queue listener on {}: {}".format(self.fqdn, e)
                message = traceback.format_exc()
                self.logger.error("{} handler {}".format(self.name, subject))
                self.logger.error(message)

                # problems that we didn't expect should create non-escalating
                # incidents. this event will not automatically clear.
                self.events.put({
                    "data": {
                        "component": {"name": "agent:{}:error".format(self.name)},
                        "severity": "3",
                        "title": subject,
                        "message": message,
                    }
                })

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
            # process each log line through the monitoring configuration
            process = event["processname"]
            stream = event["channel"]

            # make sure this process is monitored for this stream
            configuration = self.configurations.configuration("log", process)
            if (configuration is not None):
                # there may be multiple regexes for each process/stream
                # combination. run each line against each regex. we will also
                # validate the regular expression and raise an event if the
                # regex is invalid
                lines = list(filter(len, data.split("\n")))
                for line in lines:
                    for monitor in configuration[stream]:
                        component = "monitor:{}:{}".format(stream, process)
                        if (monitor["name"]):
                            component = "{}:{}".format(component, monitor["name"])

                        try:
                            regex = re.compile(monitor["regex"])
                        except re.error:
                            # can't do anything else with this monitor
                            self.logger.error("{} handler invalid regular expression '{}' for {} on {}".format(self.name, monitor["regex"], process, stream))
                            break

                        if (regex.search(line)):
                            self.logger.debug("{} handler matched '{}' for {} on {}".format(self.name, monitor["regex"], process, stream))

                            # some regexes don't have severities set. in that
                            # case we do not create any events. this typically
                            # happens in combination with "stop".
                            if (monitor["severity"]):
                                self.events.put({
                                    "data": {
                                        "contact": monitor["contact"],
                                        "component": {"name": component},
                                        "severity": monitor["severity"],
                                        "message": "{}\n\n{}".format(line, data),
                                    }
                                })

                            # if the monitor matched this line and it has the
                            # "stop" configuration set then we break out of the
                            # monitors loop and then process the next line.
                            if (monitor["stop"]):
                                self.logger.debug("{} handler stopping log processing for {} on {} because of stop rule".format(self.name, process, stream))
                                break
        except Exception as e:
            subject = "unexpected error on {}: {}".format(self.fqdn, repr(e))
            message = traceback.format_exc()
            self.logger.error("{} handler {}".format(self.name, subject))
            self.logger.error(message)

            # problems that we didn't expect should create
            # non-escalating incidents. this event will not clear
            # automatically.
            self.events.put({
                "data": {
                    "component": {"name": "agent:{}:error".format(self.name)},
                    "severity": "3",
                    "title": subject,
                    "message": message,
                }
            })
