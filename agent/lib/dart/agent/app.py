import os
import sys
import logging
import select
import importlib
import socket
import time
from datetime import datetime
from queue import Queue
from threading import Event
import dart.common.event
import dart.common.configuration
from dart.common.killer import GracefulSignalKiller

# these are the handlers that we'll connect to
from .handlers.coordination import CoordinationHandler
from .handlers.configuration import ConfigurationHandler
from .handlers.scheduler import SchedulerHandler
from .handlers.log import LogHandler
from .handlers.state import StateHandler
from .handlers.probe import ProbeHandler
from .handlers.queue import QueueHandler

# import explicitly and specifically like this and NOT as a relative import.
# this is entirely so that we can check if the version number has changed. if
# it changes then we are going to exit so that we can restart ourselves.
import dart.agent


class DartAgent(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # disable the verbose logging in kombu
        if (not self.logger.isEnabledFor(logging.DEBUG)):
            logging.getLogger("kombu").setLevel(logging.INFO)
            logging.getLogger("cassandra").setLevel(logging.INFO)

        # this keeps track of whether we've been told to die or not
        self.killer = GracefulSignalKiller()

        # make sure we are an event listener
        supervisor_server_url = os.environ.get("SUPERVISOR_SERVER_URL", None)
        if (supervisor_server_url is None):
            raise RuntimeError("cannot run from outside supervisor eventlistener")
        self.logger.info("connecting to supervisor over {}".format(supervisor_server_url))

        # figure out who we are, everyone wants to know who we are
        self.hostname = socket.getfqdn()
        self.logger.info("using hostname {}".format(self.hostname))

        # this is where we will keep configurations. we will try to ensure
        # that it exists, too. this will raise an exception if the directory
        # can't be created. that's ok, let it bubble up to the caller.
        configuration = dart.common.configuration.load()
        configuration_path = configuration["configuration"]["path"]
        self.logger.info("writing configuration files to {}".format(configuration_path))
        os.makedirs(configuration_path, mode=0o755, exist_ok=True)

        # these are the actual configuration files for the handlers. these
        # should be found under "configuration_path".
        supervisor_configuration_file = "supervisord.conf"
        scheduler_configuration_file = "scheduler.conf"
        monitor_configuration_file = "monitor.conf"

        # setting these will trigger a reread or a rewrite
        self.reread_trigger = Event()
        self.rewrite_trigger = Event()

        # anything put onto this queue will get sent to the message bus, as
        # long as it meets the correct format which is basically:
        #
        #    dict(
        #        exchange="exchange-name",
        #        payload=dict(
        #            foo=bar,
        #            baz=bat
        #        )
        #    )
        #
        self.queue = Queue()

        # these are the handlers that we're working with. they get processed in
        # the order in which they appear in this array.
        self.handlers = [
            # this listens to the message bus for actions to perform locally.
            # actions might be rereading or rewriting configurations or
            # commands to stop, start, or restart processes.
            CoordinationHandler(
                supervisor_server_url=supervisor_server_url,
                reread_trigger=self.reread_trigger,
                rewrite_trigger=self.rewrite_trigger,
            ),

            # this loads supervisor, scheduler, and monitoring configurations
            # and writes them to their respective files. it writes new files
            # when the rewrite_trigger is set. after writing new files this
            # sets the reread_trigger so that everything reloads their
            # configurations from the new files.
            ConfigurationHandler(
                configuration_path=configuration_path,
                supervisor_configuration_file=supervisor_configuration_file,
                scheduler_configuration_file=scheduler_configuration_file,
                monitor_configuration_file=monitor_configuration_file,
                reread_trigger=self.reread_trigger,
                rewrite_trigger=self.rewrite_trigger,
            ),

            # this launches processes on a schedule using configurations in the
            # file written by the configuration handler above.
            SchedulerHandler(
                supervisor_server_url=supervisor_server_url,
                configuration_path=configuration_path,
                configuration_file=scheduler_configuration_file,
                rewrite_trigger=self.rewrite_trigger,
            ),

            # this listens for log messages and checks them against the log
            # monitoring configurations.
            LogHandler(
                configuration_path=configuration_path,
                configuration_file=monitor_configuration_file,
                reread_trigger=self.reread_trigger,
                rewrite_trigger=self.rewrite_trigger,
            ),

            # this listens for state changes and checks them against the state
            # monitoring configurations. it also sends state changes to the
            # message bus so that they can be recorded more quickly.
            StateHandler(
                queue=self.queue,
                supervisor_server_url=supervisor_server_url,
                configuration_path=configuration_path,
                configuration_file=monitor_configuration_file,
                reread_trigger=self.reread_trigger,
                rewrite_trigger=self.rewrite_trigger,
            ),

            # this probes system configurations such as active processes,
            # pending processes, and system state, and puts it onto the message
            # bus using the queue. this also monitors active configurations and
            # raises alerts for daemon and state monitors. finally, this raises
            # events for any process that is in a pending state.
            ProbeHandler(
                queue=self.queue,
                supervisor_server_url=supervisor_server_url,
                configuration_path=configuration_path,
                configuration_file=monitor_configuration_file,
                reread_trigger=self.reread_trigger,
                rewrite_trigger=self.rewrite_trigger,
            ),

            # this sends events from the queue to the message bus. this needs
            # to be stopped last because we want to be able to flush the queue
            # before shutting down.
            QueueHandler(
                queue=self.queue,
            )
        ]

    def run(self, *args, **kwargs):
        # start all of the handlers
        for handler in self.handlers:
            self.logger.debug("starting handler: {}".format(handler.name))
            handler.start()

        # if we need to exit then this will be changed to True
        finished = False

        while (not finished):
            # transition from ACKNOWLEDGED to READY
            print("READY\n", flush=True, end="")

            # this flag will be set if we were processing something when we
            # decided to exit. if we were in the middle of processing something
            # then we need to acknowledge it before exiting.
            needs_acknowledgement = False

            # try to read from stdin. if we've received nothing then it means
            # that nothing was sent within the timeout and we should try again.
            # however, upon every timeout we will check to see if we were sent
            # a signal to exit. the ONLY time we check that signal is here and
            # we ONLY check the signal here and nothing else. this is because
            # if the event listener is busy then we will not usually ever reach
            # the timeout. in fact, if the event listener is at all busy then
            # only time we will ever reach the timeout is when supervisor has
            # signalled the event listener to exit and thus has stopped sending
            # events. in that scenario we'd never reach a TICK but we would
            # reach a timeout. if there are other things to be done on some
            # interval then put them into the TICK processing routine.
            while (not self.killer.killed()):
                try:
                    parts = self._read_message(sys.stdin.buffer)
                    if (parts is None):
                        # reached a timeout, see if we were killed
                        self.logger.debug("timed out")
                    else:
                        # if the event handling routine returns "true" then we
                        # should keep processing events. false means that we are
                        # finished processing events. we might be finished if
                        # our version number changed.
                        finished = not self._handle_event(*parts)

                        # we were just processing something so we need to
                        # acknowledge that.
                        needs_acknowledgement = True

                        # we are currently in a loop that checks to see if
                        # something was sent over stdin and then also checks
                        # for process signals. get out of that loop
                        # immediately.
                        break
                except EOFError as e:
                    self.logger.error("received EOF from supervisor: {}".format(repr(e)))
                    # if we received an eof then we have lost our pipe to
                    # supervisor. now we must exit.
                    finished = True

                    # we are currently in a loop that checks to see if
                    # something was sent over stdin and then also checks for
                    # process signals. get out of that loop immediately.
                    break
            else:
                # break out of the "not finished" loop above.
                self.logger.info("received signal to exit")
                finished = True

            # if we decided that we're done then we are not going to send a
            # message to supervisor that we're done but only if it is waiting
            # for it.
            if (needs_acknowledgement):
                # transition from READY to ACKNOWLEDGED
                # this prints to stdout where we communicate with supervisor
                print("RESULT 2\nOK", flush=True, end="")
        else:
            self.logger.debug("finished supervisor listener loop")

        # tell the handlers to all stop
        for handler in self.handlers:
            self.logger.debug("stopping handler: {}".format(handler.name))
            handler.stop()

        # say goodnight, kevin.
        self.logger.info("gracefully exiting")

    def _read_message(self, handle):
        # wait ten seconds for a message before exiting with nothing
        while handle in select.select([handle], [], [], 1)[0]:
            # if the next line returns a false-like value then we received an
            # eof. if we have received an eof then we're going to get out
            # because something went horribly wrong.
            line = handle.readline()
            if (not line):
                raise EOFError("received eof from supervisord trying to read message header")

            # convert the line to a string
            line = line.decode("utf-8", "backslashreplace")

            # let's assume that we got a real message
            header = dict([x.split(":") for x in line.split()])
            data_length = int(header.get("len", 0))  # this will raise a value error on bad data
            if (data_length == 0):
                return (header, None, None)

            # read more to get the payload
            data = handle.read(data_length)
            if (not data):
                raise EOFError("received eof from supervisord trying to read message payload")

            # convert the data to a string
            data = data.decode("utf-8", "backslashreplace")

            if ('\n' in data):
                # this message has additional data so extract it out
                event, data = data.split('\n', 1)
                event = dict([x.split(":") for x in event.split()])
                return (header, event, data)
            else:
                event = dict([x.split(":") for x in data.split()])
                return (header, event, None)
        else:
            return

    def _handle_event(self, header, event, data):
        if (header["eventname"].startswith("TICK_")):
            self.logger.debug("received {} event".format(header["eventname"]))
            return self._handle_tick_event(header["eventname"], event, data)

        # if it's not a tick event, send it on its way to the even thandlers
        for handler in self.handlers:
            if (handler.can_handle(header["eventname"])):
                handler.handle(header["eventname"], event, data)

        # returning True means process more events. False means we exit. only
        # "tick" events can stop us from processing more things.
        return True

    def _handle_tick_event(self, event_type, event, data):
        # we are buffering all events. this allows us to restart the daemon
        # without losing anything. it also lets us handle bursts of data. but
        # we don't really want to buffer any TICK events because we really only
        # want to run those once per interval and not run a whole burst of them
        # after, say, restarting this daemon. so we will not process any tick
        # event unless the timestamp on the tick event happened within the last
        # interval. that is to say, if the event is a TICK_60 but the timestamp
        # for the tick was greater than 60 seconds ago then we're going to
        # ignore it.
        interval = int(event_type[5:])  # take the number off of the end of TICK_60
        timestamp = int(time.time())  # get the current time
        event_timestamp = int(event.get("when", 0))  # get the time of the event (only present on TICK events)
        if (timestamp - event_timestamp > interval):
            self.logger.warning("skipping {} from {} because it is older than {} seconds ({} seconds ago)".format(event_type, event_timestamp, interval, (timestamp - event_timestamp)))

            # don't bother checking to see if the version changed, just keep
            # processing things (including tick events) and eventually we'll
            # get to a recent tick and we'll check the whether our version has
            # changed.
            return True

        # send a keepalive to the monitoring system
        dart.common.event.keepalive(
            component="dart:agent",
            severity=1,
            message="dart agent not responding",
            timeout=10,  # minutes
        )

        # now that we've collapsed the tick events, issue a rewrite command
        self.logger.debug("tick handler triggering a rewrite")
        self.rewrite_trigger.set()

        # now that we've collapsed the tick events, send it to our handlers
        for handler in self.handlers:
            if (handler.can_handle(event_type)):
                handler.handle(event_type, event, data)

        # restart every monday at midnight
        event_datetime = datetime.fromtimestamp(event_timestamp)
        if (event_datetime.hour == 0 and event_datetime.minute == 0 and event_datetime.weekday() == 0):
            self.logger.info("exiting for the weekly restart")
            return False

        # finally, we periodically check to see if we need to restart ourselves
        return not self._has_version_changed()

    def _has_version_changed(self):
        try:
            old_version = dart.agent.__version__
            importlib.reload(dart.agent)
            new_version = dart.agent.__version__

            if (old_version != new_version):
                self.logger.info("new version {} is not the same as old version {}".format(new_version, old_version))
                return True
        except Exception as e:
            pass

        return False
