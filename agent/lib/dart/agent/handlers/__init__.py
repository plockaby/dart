import dart.common.event
import logging
import traceback
import socket
import json


class BaseHandler(object):
    def __init__(self, **kwargs):
        # everything needs a logger!
        self.logger = logging.getLogger(__name__)

        # figure out who we are, everyone wants to know who we are
        self.fqdn = socket.getfqdn()

    @property
    def name(self):
        raise NotImplementedError("property must be implemented in subclass")

    def can_handle(self, event_type):
        raise NotImplementedError("must be implemented in subclass")

    def handle(self, event_type, event, data):
        raise NotImplementedError("must be implemented in subclass")

    def start(self):
        raise NotImplementedError("must be implemented in subclass")

    def stop(self):
        raise NotImplementedError("must be implemented in subclass")

    def _load_configuration(self, configuration_path, configuration_file):
        try:
            with open("{}/{}".format(configuration_path, configuration_file), "r") as f:
                configuration = json.load(f)

            # if we were able to successfully load the configuration file then
            # clear any errors saying that we weren't able to load it.
            dart.common.event.send(
                component="dart:agent:{}:configuration".format(self.name),
                severity=6,
                subject="clear",
            )

            # then return the configuration so it can be loaded wherever
            return configuration
        except json.JSONDecodeError as e:
            subject = "{} handler found invalid json in {}/{}".format(self.name, configuration_path, configuration_file)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)

            # this is a system error, create a non-escalating incident. this
            # is automatically cleared as soon as we get valid json.
            dart.common.event.send(
                component="dart:agent:{}:configuration".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )

            # trigger a rewrite of the configuration file
            self.logger.info("{} handler triggering a rewrite".format(self.name))
            self.rewrite_trigger.set()
        except OSError as e:
            subject = "{} handler could not read file {}/{}".format(self.name, configuration_path, configuration_file)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)

            # this is a system error, create a non-escalating incident. this
            # is automatically cleared as soon as we can read the json file.
            dart.common.event.send(
                component="dart:agent:{}:configuration".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )

            # trigger a rewrite of the configuration file
            self.logger.info("{} handler triggering a rewrite".format(self.name))
            self.rewrite_trigger.set()
        except Exception as e:
            subject = "{} handler unexpected error reading file {}/{}: {}".format(self.name, configuration_path, configuration_file, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # problems that we didn't expect should create non-escalating
            # incidents. this event will not automatically clear.
            dart.common.event.send(
                component="dart:agent:{}:configuration:error".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )
