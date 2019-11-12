"""
This handler, when signaled, gets the active and pending configurations from
supervisord and posts to the DartAPI.
"""

from . import BaseHandler
from ..settings import SettingsManager
from ..configurations import ConfigurationsManager
import dart.agent.api
from dart.common.supervisor import SupervisorClient
from dart.common.killer import GracefulEventKiller
from threading import Thread
import xmlrpc.client
import urllib.parse
import requests
import traceback
import json


class ProbeHandler(BaseHandler):
    def __init__(self, supervisor_server_url, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # get program settings into ourselves
        self.settings = SettingsManager().get("monitor", {})
        self.configurations = ConfigurationsManager()

        # keep track of where to find the supervisor socket
        self.supervisor_server_url = supervisor_server_url

        # we can set these to force a reread or a rewrite
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

    @property
    def name(self):
        return "probe"

    def start(self):
        # this thread listens for the reread trigger and then probes the system
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the thread to stop using a thread safe mechanism
        self.killer.kill()

        # then wait for our thread to be finished
        self.thread.join()

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle since we can't handle anything
        pass

    # this method runs in a thread
    def _run(self):
        while (not self.killer.killed()):
            if (self.reread_trigger.wait(timeout=1)):
                try:
                    # probe supervisor configurations
                    self._probe_active_supervisor_configurations()
                    self._probe_pending_supervisor_configurations()

                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}".format(self.name)},
                            "severity": "OK",
                            "message": "clear",
                        }
                    })
                except xmlrpc.client.Fault as e:
                    # don't want to raise any alarms about this one
                    subject = "could not probe supervisor on {}: {}".format(self.fqdn, e.faultString)
                    message = traceback.format_exc()
                    self.logger.warning("{} handler {}".format(self.name, subject))
                    self.logger.warning(message)

                    # errors talking to supervisor should create escalating
                    # incidents because we might need to restart supervisord.
                    # this will clear automatically.
                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}".format(self.name)},
                            "severity": "2",
                            "subject": subject,
                            "message": message,
                        }
                    })
                except Exception as e:
                    subject = "unexpected error on {}: {}".format(self.fqdn, e)
                    message = traceback.format_exc()
                    self.logger.error("{} handler {}".format(self.name, subject))
                    self.logger.error(message)

                    # this is an unexpected error so raise a different event
                    # for it. this event will NOT automatically clear.
                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}:error".format(self.name)},
                            "severity": "3",
                            "subject": subject,
                            "message": message,
                        }
                    })
                finally:
                    # this clears the trigger so that it can be pulled again
                    self.reread_trigger.clear()

        # tell everything that we're done
        self.logger.info("{} handler exiting".format(self.name))

    def _probe_active_supervisor_configurations(self):
        self.logger.debug("{} handler probing active supervisor configurations".format(self.name))

        # get active processes
        client = SupervisorClient(self.supervisor_server_url)
        states = client.connection.supervisor.getAllProcessInfo()

        try:
            # send active processes to the DartAPI. it's ok if this fails
            # because we'll just try again in a minute. we still want to update
            # the CorkAPI so we'll keep going.
            url = "{}/agent/v1/active/{}".format(dart.agent.api.DART_API_URL, urllib.parse.quote(self.fqdn))
            response = dart.agent.api.dart.post(url, data=json.dumps(states), timeout=22)
            response.raise_for_status()
        except requests.RequestException as e:
            # do not need to see this one on dash
            subject = "could not talk to the DartAPI on {}: {}".format(self.fqdn, e)
            message = traceback.format_exc()
            self.logger.warning("{} handler {}".format(self.name, subject))
            self.logger.warning(message)

        # if there are any processes that are:
        # - being daemon monitored but not running
        # - being state monitored but are failing
        # then raise an event for that. otherwise clear any alarms.
        for state in states:
            process = state["name"]

            configuration = self.configurations.configuration("state", process)
            if (configuration is not None):
                if (state["statename"] == "RUNNING"):
                    # if the process is successfully running then clear any
                    # state alerts for it.
                    self.logger.debug("{} handler clearing state event for {} on {} because it is now RUNNING".format(self.name, process, self.fqdn))
                    self.events.put({
                        "data": {
                            "contact": configuration["contact"],
                            "component": {"name": "monitor:state:{}".format(process)},
                            "severity": "OK",
                            "message": "clear",
                        }
                    })
                else:
                    # if this process is being state monitored and it has gone
                    # into one of these error states then raise an error.
                    if (state["statename"] in ["UNKNOWN", "FATAL", "BACKOFF"]):
                        self.logger.debug("{} handler raising state event for {} on {} because it has gone into state {}".format(self.name, process, self.fqdn, state["statename"]))
                        self.events.put({
                            "data": {
                                "contact": configuration["contact"],
                                "component": {"name": "monitor:state:{}".format(process)},
                                "severity": configuration["severity"],
                                "title": "{} on {} entered the state {}".format(process, self.fqdn, state["statename"]),
                                "message": state["spawnerr"],
                            }
                        })

                    # if this process is being state monitored and it returned
                    # an error when it exited then raise an error.
                    elif (state["spawnerr"]):
                        self.logger.debug("{} handler raising state event for {} on {} because it exited with an error".format(self.name, process, self.fqdn))
                        self.events.put({
                            "data": {
                                "contact": configuration["contact"],
                                "component": {"name": "monitor:state:{}".format(process)},
                                "severity": configuration["severity"],
                                "title": "{} on {} exited with an error".format(process, self.fqdn),
                                "message": state["spawnerr"],
                            }
                        })

            configuration = self.configurations.configuration("daemon", process)
            if (configuration is not None):
                if (state["statename"] == "RUNNING"):
                    self.logger.debug("{} handler clearing state event for {} on {} because it is now RUNNING".format(self.name, process, self.fqdn))
                    # if the process is successfully running then clear any
                    # daemon alerts for it.
                    self.events.put({
                        "data": {
                            "contact": configuration["contact"],
                            "component": {"name": "monitor:daemon:{}".format(process)},
                            "severity": "OK",
                            "message": "clear",
                        }
                    })
                else:
                    self.logger.debug("{} handler raising daemon event for {} on {} because it is in state {} when it is supposed to be in state RUNNING".format(self.name, process, self.fqdn, state["statename"]))
                    self.events.put({
                        "data": {
                            "contact": configuration["contact"],
                            "component": {"name": "monitor:daemon:{}".format(process)},
                            "severity": configuration["severity"],
                            "message": "{} on {} is in state {} when it is supposed to be in state RUNNING".format(process, self.fqdn, state["statename"]),
                        }
                    })

    def _probe_pending_supervisor_configurations(self):
        # get pending process changes
        client = SupervisorClient(self.supervisor_server_url)
        states = client.connection.supervisor.reloadConfig()

        # make the list easier to read. something in the supervisord
        # rpcinterface documentation about not being able to return an
        # array with a length greater than one. so this is what we get.
        pending = {
            "added": states[0][0],
            "changed": states[0][1],
            "removed": states[0][2],
        }

        try:
            # send pending processes to the DartAPI. it's ok if this fails
            # because we'll just try again in a minute. we still want to update
            # the CorkAPI so we'll keep going.
            url = "{}/agent/v1/pending/{}".format(dart.agent.api.DART_API_URL, urllib.parse.quote(self.fqdn))
            response = dart.agent.api.dart.post(url, data=json.dumps(pending), timeout=22)
            response.raise_for_status()
        except requests.RequestException as e:
            # do not need to see this one on dash
            subject = "could not talk to the DartAPI on {}: {}".format(self.fqdn, e)
            message = traceback.format_exc()
            self.logger.warning("{} handler {}".format(self.name, subject))
            self.logger.warning(message)

        # if there are any pending changes then raise an event for that
        if (len(pending["added"]) or len(pending["removed"]) or len(pending["changed"])):
            subject = []
            if (len(pending["added"])):
                subject.append("{} added".format(",".join(pending["added"])))
            if (len(pending["removed"])):
                subject.append("{} removed".format(",".join(pending["removed"])))
            if (len(pending["changed"])):
                subject.append("{} changed".format(",".join(pending["changed"])))

            self.logger.debug("raising severity 4 event for {}".format("; ".join(subject)))
            self.events.put({
                "data": {
                    "component": {"name": "monitor:pending"},
                    "severity": "4",
                    "message": "; ".join(subject),
                }
            })
        else:
            # clear pending change events
            self.events.put({
                "data": {
                    "component": {"name": "monitor:pending"},
                    "severity": "OK",
                    "message": "clear",
                }
            })
