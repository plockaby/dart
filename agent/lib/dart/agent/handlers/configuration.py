"""
This handler, when signaled, queries the DartAPI for updated configuration
information for this host. It then updates the supervisord configuration on
disk, updates the shared configurations for monitoring and scheduling, and
triggers a reread of all configurations.
"""

from . import BaseHandler
from ..configurations import ConfigurationsWriter
from dart.common.killer import GracefulEventKiller
from threading import Thread
import requests
import traceback


class ConfigurationHandler(BaseHandler):
    def __init__(self, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # we can set these to force a reread or a rewrite
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

    @property
    def name(self):
        return "configuration"

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

        # trigger the event using a thread safe mechanism
        self.killer.kill()

        # then wait for our thread to be finished
        self.thread.join()

    # this runs inside of a thread
    def _run(self):
        # if we haven't received a kill signal then wait for a trigger telling
        # us to rewrite our configurations. that trigger is set every sixty
        # seconds by TICK events or when we receive a message from the
        # coordination handler.
        while (not self.killer.killed()):
            if (self.rewrite_trigger.wait(timeout=1)):
                try:
                    ConfigurationsWriter().write()

                    # clear the transient error events
                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}".format(self.name)},
                            "severity": "OK",
                            "message": "clear",
                        }
                    })
                except requests.RequestException as e:
                    subject = "could not talk to the DartAPI on {}: {}".format(self.fqdn, e)
                    message = traceback.format_exc()
                    self.logger.warning("{} handler {}".format(self.name, subject))
                    self.logger.warning(message)

                    # this is a system error, create a escalating incident.
                    # this event will automatically clear if we are able to
                    # successfully write our configurations.
                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}".format(self.name)},
                            "severity": 2,  # high severity
                            "title": subject,
                            "message": message,
                        }
                    })
                except OSError as e:
                    subject = "could not write configuration files on {}: {}".format(self.fqdn, e)
                    message = traceback.format_exc()
                    self.logger.warning("{} handler {}".format(self.name, subject))
                    self.logger.warning(message)

                    # this is a system error, create a escalating incident.
                    # this event will automatically clear if we are able to
                    # successfully write our configurations.
                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}".format(self.name)},
                            "severity": 2,  # high severity
                            "title": subject,
                            "message": message,
                        }
                    })
                except Exception as e:
                    subject = "unexpected error on {}: {}".format(self.fqdn, e)
                    message = traceback.format_exc()
                    self.logger.error("{} handler {}".format(self.name, subject))
                    self.logger.error(message)

                    # problems that we didn't expect should create
                    # non-escalating incidents. this event will not clear
                    # automatically.
                    self.events.put({
                        "data": {
                            "component": {"name": "agent:{}:error".format(self.name)},
                            "severity": 3,  # medium severity
                            "title": subject,
                            "message": message,
                        }
                    })
                finally:
                    # this clears the trigger so that it can be set again
                    self.rewrite_trigger.clear()

                    # now trigger a reread to pick up the configurations that
                    # just finished writing. if the trigger is already set then
                    # we will wait before trying to set it again.
                    self.logger.info("{} handler triggering a reread".format(self.name))
                    self.reread_trigger.set()

        # tell everything that we're done
        self.logger.info("{} handler exiting".format(self.name))
