"""
This handler, when signaled, checks all configured schedules and start programs
as necessary.
"""

from . import BaseHandler
from ..settings import SettingsManager
from ..configurations import ConfigurationsManager
import xmlrpc.client
from dart.common.supervisor import SupervisorClient
from crontab import CronTab
from datetime import datetime
import traceback


class SchedulerHandler(BaseHandler):
    def __init__(self, supervisor_server_url, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # get program settings into ourselves
        self.settings = SettingsManager().get("monitor", {})
        self.configurations = ConfigurationsManager()

        # we can set these to force a reread or a rewrite
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we connect to supervisor
        self.supervisor_server_url = supervisor_server_url

    @property
    def name(self):
        return "scheduler"

    def start(self):
        pass

    def stop(self):
        pass

    def can_handle(self, event_type):
        return (event_type == "TICK_60")

    def handle(self, event_type, event, data):
        # use the timestamp from the event
        timestamp = int(event.get("when", 0))

        # get the configuration once because it's kind of expensive
        schedules = self.configurations.schedules()

        for process_name, schedule in schedules.items():
            self.logger.debug("checking crontab for {}: {}".format(process_name, schedule))

            try:
                crontab = CronTab(schedule)
            except ValueError:
                subject = "invalid crontab for {} on {}: {}".format(process_name, self.fqdn, schedule)
                message = traceback.format_exc()
                self.logger.warning("{} handler {}".format(self.name, subject))
                self.logger.warning(message)

                # if the crontab is misconfigured, create a non-escalating
                # incident. this event will automatically clear as soon as
                # we get a valid crontab for this item. it is possible that
                # this would need to be manually cleared if the process
                # disappears from the schedule file never to be seen again.
                self.events.put({
                    "data": {
                        "component": {"name": "agent:{}:{}:configuration".format(self.name, process_name)},
                        "severity": "3",
                        "title": subject,
                        "message": message,
                    }
                })
            else:
                # clear any existing errors related to reading the crontab
                # for this process. if any errors come up trying to run the
                # process then the alert will be recreated.
                self.events.put({
                    "data": {
                        "component": {"name": "agent:{}:{}:configuration".format(self.name, process_name)},
                        "severity": "OK",
                        "message": "clear",
                    }
                })

                # because the timestamp we get is spot on the minute and
                # because the crontab module tells us the NEXT time
                # something will run, we need to subtract one second from
                # the given timestamp to see if the process in question
                # should run right now.
                if ((crontab.next(datetime.fromtimestamp(timestamp - 1), default_utc=True) - 1) == 0):
                    self.logger.info("{} handler starting {}".format(self.name, process_name))
                    try:
                        client = SupervisorClient(self.supervisor_server_url)
                        client.connection.supervisor.startProcess(process_name, False)

                        # clear any existing errors related to processing
                        # the crontab for this process.
                        self.events.put({
                            "data": {
                                "component": {"name": "agent:{}:{}".format(self.name, process_name)},
                                "severity": "OK",
                                "message": "clear",
                            }
                        })
                    except xmlrpc.client.Fault as e:
                        subject = "could not start process {} on {}: {}".format(process_name, self.fqdn, e.faultString)
                        message = traceback.format_exc()
                        self.logger.warning("{} handler {}".format(self.name, subject))
                        self.logger.warning(message)

                        # if we can't start the process then we care, but
                        # only informationally.
                        self.events.put({
                            "data": {
                                "component": {"name": "agent:{}:{}".format(self.name, process_name)},
                                "severity": "4",
                                "title": subject,
                                "message": message,
                            }
                        })
                    except Exception as e:
                        subject = "could not start process {} on {}: {}".format(process_name, self.fqdn, repr(e))
                        message = traceback.format_exc()
                        self.logger.warning("{} handler {}".format(self.name, subject))
                        self.logger.warning(message)

                        # this is an unexpected error so create a
                        # non-escalating incident for it. this error will
                        # not clear automatically. this is tied to the
                        # scheduler and not to the item being scheduled.
                        self.events.put({
                            "data": {
                                "component": {"name": "agent:{}:error".format(self.name)},
                                "severity": "3",
                                "title": subject,
                                "message": message,
                            }
                        })
