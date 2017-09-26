import sys
import socket


def patch():
    # call both, see which one works
    eventlet_patch()
    if (is_eventlet_patched()):
        return True

    gevent_patch()
    if (is_gevent_patched()):
        return True

    return False


def eventlet_patch():
    if "eventlet" in sys.modules:
        import eventlet
        eventlet.monkey_patch()


def gevent_patch():
    if "gevent" in sys.modules:
        from gevent import monkey
        monkey.patch_all()


def is_eventlet_patched():
    if "eventlet.patcher" not in sys.modules:
        return False
    import eventlet.patcher
    return eventlet.patcher.is_monkey_patched("socket")


def is_gevent_patched():
    if "gevent.monkey" not in sys.modules:
        return False
    import gevent.socket
    return socket.socket is gevent.socket.socket
