import logging
import socket


class BaseHandler(object):
    def __init__(self, events, **kwargs):
        # everything needs a logger!
        self.logger = logging.getLogger(__name__)

        # figure out who we are, everyone wants to know who we are
        self.fqdn = socket.getfqdn()

        # universal access to our event queue
        self.events = events

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
