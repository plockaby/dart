import socket


# only load the hostname once
localhost = socket.getfqdn()


def send(component, severity, subject, message="", contact=None, hostname=None, timeout=None):
    # default hostname is us
    if (hostname is None):
        hostname = localhost

    # TODO - implement notification system
