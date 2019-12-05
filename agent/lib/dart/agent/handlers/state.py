"""
This handler listens for state change events and if they match a monitoring
configuration creates an event. It also posts state changes to the DartAPI to
update the central data store.
"""

from . import BaseHandler
from ..configurations import ConfigurationsManager
from dart.common.supervisor import SupervisorClient
from dart.common.killer import GracefulEventKiller
import dart.agent.api
from threading import Thread
from queue import Queue
import xmlrpc.client
import urllib.parse
import requests
import traceback
import json


class StateHandler(BaseHandler):
    def __init__(self, supervisor_server_url, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # get program settings into ourselves
        self.configurations = ConfigurationsManager()

        # this is how we connect to supervisor
        self.supervisor_server_url = supervisor_server_url

        # used to trigger configuration file rewrites
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

        # all states are received and put on a queue for processing. this is
        # that queue. "processing" means checking supervisord for current state
        # and sending that state to dart.
        self.processor = Queue()

    @property
    def name(self):
        return "state"

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
        return event_type.startswith("PROCESS_STATE_")

    def handle(self, event_type, event, data):
        self.processor.put({"type": event_type, "event": event})

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
                    self._check(item["type"], item["event"])
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
            # get the process information from supervisor
            client = SupervisorClient(self.supervisor_server_url)
            state = client.connection.supervisor.getProcessInfo(event["processname"])

            # process the state message through the monitoring configuration
            process = state["name"]

            try:
                # send the state message to the DartAPI. it's ok if this fails
                # because the probe handler updates all process states every
                # minute. we still want to update the CorkAPI so we're going
                # to catch this error here and then keep going.
                self.logger.debug("recording state change on {} to {}".format(event["processname"], event_type))
                url = "{}/agent/v1/state/{}/{}".format(dart.agent.api.DART_API_URL, urllib.parse.quote(self.fqdn), urllib.parse.quote(process))
                response = dart.agent.api.dart.post(url, data=json.dumps(state), timeout=22)
                response.raise_for_status()
            except requests.RequestException as e:
                # don't want to raise any alarms about this one
                subject = "{} handler could not post to the DartAPI: {}".format(self.name, e)
                message = traceback.format_exc()
                self.logger.warning(subject)
                self.logger.warning(message)

            configuration = self.configurations.configuration("state", process)
            if (configuration is not None):
                if (state["statename"] == "RUNNING"):
                    # if the process is successfully running then clear event
                    self.logger.debug("{} handler clearing state event for {} because it is now RUNNING".format(self.name, process))
                    self.events.put({
                        "data": {
                            "ci": configuration["ci"],
                            "component": {"name": "monitor:state:{}".format(process)},
                            "severity": "OK",
                            "message": "clear",
                        }
                    })
                else:
                    # if this process is being state monitored and it has gone
                    # into one of these error states then raise an error.
                    if (state["statename"] in ["UNKNOWN", "FATAL", "BACKOFF"]):
                        self.logger.debug("{} handler raising state event for {} because it has gone into state {}".format(self.name, process, state["statename"]))
                        self.events.put({
                            "data": {
                                "ci": configuration["ci"],
                                "component": {"name": "monitor:state:{}".format(process)},
                                "severity": configuration["severity"],
                                "message": "{} on {} entered the state {}\n\n{}".format(process, self.fqdn, state["statename"], state["spawnerr"]),
                            }
                        })

                    # if this process is being state monitored and it returned
                    # an error when it exited then raise an error.
                    elif (state["spawnerr"]):
                        self.logger.debug("{} handler raising state event for {} because it exited with an error".format(self.name, process))
                        self.events.put({
                            "data": {
                                "ci": configuration["ci"],
                                "component": {"name": "monitor:state:{}".format(process)},
                                "severity": configuration["severity"],
                                "message": "{} on {} exited with an error\n\n{}".format(process, self.fqdn, state["spawnerr"]),
                            }
                        })

            configuration = self.configurations.configuration("daemon", process)
            if (configuration is not None):
                if (state["statename"] == "RUNNING"):
                    # if the process is successfully running then clear any
                    # daemon alerts for it.
                    self.logger.debug("{} handler clearing daemon event for {} because it is now RUNNING".format(self.name, process))
                    self.events.put({
                        "data": {
                            "ci": configuration["ci"],
                            "component": {"name": "monitor:daemon:{}".format(process)},
                            "severity": "OK",
                            "message": "clear",
                        }
                    })

                else:
                    self.logger.debug("{} handler raising daemon event for {} because it is in state {} when it is supposed to be in state RUNNING".format(self.name, process, state["statename"]))
                    self.events.put({
                        "data": {
                            "ci": configuration["ci"],
                            "component": {"name": "monitor:daemon:{}".format(process)},
                            "severity": configuration["severity"],
                            "message": "{} on {} is in state {} when it is supposed to be in state RUNNING".format(process, self.fqdn, state["statename"]),
                        }
                    })

            configuration = self.configurations.configuration("keepalive", process)
            if (configuration is not None):
                # supervisor resets the "spawnerr" value when it enters the
                # "running" state so only send the keepalive when the program
                # exits without an error.
                if (state["statename"] == "EXITED" and not state["spawnerr"]):
                    self.logger.debug("{} handler sending keepalive event for {} because it EXITED without a spawn error".format(self.name, process))
                    self.events.put({
                        "type": "keepalive",
                        "data": {
                            "ci": configuration["ci"],
                            "component": {"name": "monitor:keepalive:{}".format(process)},
                            "severity": configuration["severity"],
                            "timeout": configuration["timeout"],
                            "message": "{} has stopped responding on {}".format(process, self.fqdn),
                        }
                    })

        except xmlrpc.client.Fault as e:
            # don't want to raise any alarms about this one
            subject = "{} handler could not get process state from supervisor: {}".format(self.name, e.faultString)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)
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
