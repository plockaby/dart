from threading import Event


class GracefulSignalKiller:
    # note that the logging module explicitly says that we should NOT use it
    # inside signal handlers because of thread-safety issues. so we're not.
    def __init__(self):
        import signal
        self.event = Event()
        signal.signal(signal.SIGINT, self.kill)
        signal.signal(signal.SIGTERM, self.kill)

    def kill(self, signal_number, signal_stack):
        self.event.set()

    def killed(self, timeout=0):
        return self.event.wait(timeout=timeout)


class GracefulEventKiller:
    def __init__(self):
        self.event = Event()

    def kill(self):
        self.event.set()

    def killed(self, timeout=0):
        return self.event.wait(timeout=timeout)
