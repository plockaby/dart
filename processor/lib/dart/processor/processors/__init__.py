import logging
import socket
import time
import dart.common.event


class BaseProcessor(object):
    def __init__(self, session, **kwargs):
        # everything needs a logger!
        self.logger = logging.getLogger(__name__)

        # this should be a connection to cassandra
        self.session = session

        # who we are for keepalive purposes
        self.fqdn = socket.getfqdn()

        # the last time we sent a keepalive
        self.last_keepalive = None

    @property
    def name(self):
        raise NotImplementedError("{}: property must be implemented in subclass".format(__name__))

    def process_task(self, body, message):
        raise NotImplementedError("{}: method must be implemented in subclass".format(__name__))

    def _send_keepalive(self):
        # raise an alarm if our event listener never processes anything
        if (self.last_keepalive is None or (int(time.time()) - 30) > self.last_keepalive):
            dart.common.event.keepalive(
                component="dart:processor:{}".format(self.name),
                severity=1,
                message="dart {} processor stopped processing".format(self.name),
                timeout=15,  # minutes
                hostname=self.fqdn,
            )
            self.last_keepalive = int(time.time())
