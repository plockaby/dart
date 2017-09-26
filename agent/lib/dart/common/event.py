import socket
import logging


# only load the hostname once
fqdn = socket.getfqdn()

# need a logger
logger = logging.getLogger(__name__)


def keepalive(component, severity, message, timeout, contact=None, hostname=None):
    # default hostname is us
    if (hostname is None):
        hostname = fqdn

    # set a default configuration item
    if (contact is None):
        contact = "me@example.com"

    # TODO - implement keepalive system
    logger.warning("keepalive not sent -- not implemented")


def send(component, severity, subject, message="", contact=None, hostname=None, origin=None):
    # default hostname is us
    if (hostname is None):
        hostname = fqdn
    if (origin is None):
        origin = hostname

    # set a default configuration item
    if (not contact):
        contact = "me@example.com"

    # TODO - implement notification system
    if (severity < 6):
        logger.error("{} {} {} {}".format(component, severity, subject, message))
