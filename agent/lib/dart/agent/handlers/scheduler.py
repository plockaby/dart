from . import BaseHandler
import xmlrpc.client
import dart.common.event
from dart.common.supervisor import SupervisorClient
from crontab import CronTab
from datetime import datetime
import traceback
import time


class SchedulerHandler(BaseHandler):
    def __init__(self, supervisor_server_url, configuration_path, configuration_file, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # this is how we connect to supervisor
        self.supervisor_server_url = supervisor_server_url

        # this is where we will try to read configurations
        self.configuration_path = configuration_path
        self.configuration_file = configuration_file

        # used to trigger configuration file rewrites
        self.rewrite_trigger = rewrite_trigger

        # this is the configuration that we've loaded
        self.configuration = None

    @property
    def name(self):
        return "scheduler"

    def start(self):
        # try to load our configuration file
        self.logger.debug("{} handler reading configuration".format(self.name))
        while (self.configuration is None):
            self.configuration = self._load_configuration(self.configuration_path, self.configuration_file)

            # if our monitoring configuration is still empty then we will
            # wait for them to become available.
            if (self.configuration is None):
                self.logger.warning("{} handler sleeping before trying to read configurations again".format(self.name))
                time.sleep(1)

    def stop(self):
        pass

    def can_handle(self, event_type):
        return (event_type == "TICK_60")

    def handle(self, event_type, event, data):
        # use the timestamp from the event
        timestamp = int(event.get("when", 0))

        # don't just blindly load the configuration. ensure that we are able to
        # actually load the file before replacing what we have right now.
        configuration = self._load_configuration(self.configuration_path, self.configuration_file)
        if (configuration is not None):
            self.configuration = configuration
        else:
            self.logger.warning("{} handler not replacing a good configuration with a bad configuration".format(self.name))

        for key, value in self.configuration.items():
            self.logger.debug("checking crontab for {}: {}".format(key, value))

            try:
                crontab = CronTab(value)
            except ValueError as e:
                subject = "{} handler invalid crontab for {}: {}".format(self.name, key, value)
                message = traceback.format_exc()
                self.logger.warning(subject)
                self.logger.warning(message)

                # if the crontab is misconfigured, create a non-escalating
                # incident. this event will automatically clear as soon as
                # we get a valid crontab for this item. it is possible that
                # this would need to be manually cleared if the process
                # disappears from the schedule file never to be seen again.
                dart.common.event.send(
                    component="dart:agent:{}:{}:configuration".format(self.name, key),
                    severity=2,
                    subject=subject,
                    message=message,
                )
            else:
                # clear any existing errors related to reading the crontab
                # for this process. if any errors come up trying to run the
                # process then the alert will be recreated.
                dart.common.event.send(
                    component="dart:agent:{}:{}:configuration".format(self.name, key),
                    severity="OK",
                    subject="clear",
                )

                # because the timestamp we get is spot on the minute and
                # because the crontab module tells us the NEXT time
                # something will run, we need to subtract one second from
                # the given timestamp to see if the process in question
                # should run right now.
                if ((crontab.next(datetime.fromtimestamp(timestamp - 1), default_utc=True) - 1) == 0):
                    self.logger.info("{} handler starting {}".format(self.name, key))
                    try:
                        client = SupervisorClient(self.supervisor_server_url)
                        client.connection.supervisor.startProcess(key, False)

                        # clear any existing errors related to processing
                        # the crontab for this process.
                        dart.common.event.send(
                            component="dart:agent:{}:{}".format(self.name, key),
                            severity="OK",
                            subject="clear",
                        )
                    except xmlrpc.client.Fault as e:
                        subject = "{} handler could not start process {}: {}".format(self.name, key, e.faultString)
                        message = traceback.format_exc()
                        self.logger.warning(subject)
                        self.logger.warning(message)

                        # if we can't start the process then we care, but
                        # only informationally.
                        dart.common.event.send(
                            component="dart:agent:{}:{}".format(self.name, key),
                            severity=4,
                            subject=subject,
                            message=message,
                        )
                    except Exception as e:
                        subject = "{} handler could not start process {}: {}".format(self.name, key, repr(e))
                        message = traceback.format_exc()
                        self.logger.warning(subject)
                        self.logger.warning(message)

                        # this is an unexpected error so create a
                        # non-escalating incident for it. this error will
                        # not clear automatically. this is tied to the
                        # scheduler and not to the item being scheduled.
                        dart.common.event.send(
                            component="dart:agent:{}:error".format(self.name),
                            severity=2,
                            subject=subject,
                            message=message,
                        )
