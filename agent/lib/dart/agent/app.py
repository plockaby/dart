import os
import io
import sys
import logging
import select
import importlib
import socket
import time
from queue import Queue
from threading import Event
from dart.common.killer import GracefulSignalKiller
import urllib.parse
import dart.agent.api
import platform
import json

# import explicitly and specifically like this and NOT as a relative import.
# this is entirely so that we can check if the version number has changed. if
# it changes then we are going to exit so that we can restart ourselves.
import dart.agent


class DartAgent(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # get configuration from options
        self.verbose = kwargs.get("verbose", False)

        # this keeps track of whether we've been told to die or not
        self.killer = GracefulSignalKiller()

        # figure out who we are, everyone wants to know who we are
        self.fqdn = socket.getfqdn()
        self.logger.info("using fully qualified domain name {}".format(self.fqdn))

        # setting these will trigger a reread or a rewrite
        self.reread_trigger = Event()
        self.rewrite_trigger = Event()

        # anything put onto this queue will get sent to the CorkAPI. it should
        # look like a valid CorkAPI message.
        self.events = Queue()

        # an array of all of the handlers that were started. this is populated
        # on the call to run() below
        self.handlers = []

    def run(self, *args, **kwargs):
        # initialize the settings manager
        from .settings import SettingsManager
        self.settings = SettingsManager()

        # load configurations immediately on start (onto disk, into memory)
        from .configurations import ConfigurationsWriter
        ConfigurationsWriter().write()

        # if we're just writing configurations then exit immediately
        if (kwargs.get("write_configuration")):
            self.logger.info("writing configuration files and exiting")
            return 0

        # make sure we are an event listener
        supervisor_server_url = os.environ.get("SUPERVISOR_SERVER_URL")
        if (supervisor_server_url is None):
            raise RuntimeError("cannot run from outside of a supervisor eventlistener")
        self.logger.info("connecting to supervisor over {}".format(supervisor_server_url))

        # tell dart about the system
        self._update_system_configuration()

        # this handler listens for TCP/UDP/Unix connections from the local
        # host. those connections send us events that will be forwarded to the
        # CorkAPI. this handler will also listen for events from the agent
        # itself and forward those to the CorkAPI as well.
        from .handlers.events import EventHandler
        self.handlers.append(EventHandler(events=self.events))

        # this handler listens for TCP connections from the world. those
        # connections will send us messages for actions to perform such as
        # rereading configurations, rewriting configurations, starting or
        # stopping a process, or updating supervisord. all connections must
        # come in with a valid and authorized client certificate.
        from .handlers.coordination import CoordinationHandler
        self.handlers.append(CoordinationHandler(
            events=self.events,
            supervisor_server_url=supervisor_server_url,
            reread_trigger=self.reread_trigger,
            rewrite_trigger=self.rewrite_trigger,
        ))

        # this handler, when signaled, queries the DartAPI for updated
        # configuration information for this host. it then updates the
        # supervisord configuration on disk, updates the shared configurations
        # for monitoring and scheduling, and triggers a reread of all
        # configurations.
        from .handlers.configuration import ConfigurationHandler
        self.handlers.append(ConfigurationHandler(
            events=self.events,
            reread_trigger=self.reread_trigger,
            rewrite_trigger=self.rewrite_trigger,
        ))

        # this handler, when signaled, gets the active and pending
        # configurations from supervisord and posts those to the DartAPI.
        from .handlers.probe import ProbeHandler
        self.handlers.append(ProbeHandler(
            events=self.events,
            supervisor_server_url=supervisor_server_url,
            reread_trigger=self.reread_trigger,
            rewrite_trigger=self.rewrite_trigger,
        ))

        # this handler listens for state change events and if they match a
        # monitoring configuration creates an event. It also posts state
        # changes to the DartAPI to update the central data store.
        from .handlers.state import StateHandler
        self.handlers.append(StateHandler(
            events=self.events,
            supervisor_server_url=supervisor_server_url,
            reread_trigger=self.reread_trigger,
            rewrite_trigger=self.rewrite_trigger,
        ))

        # this handler listens for log events and if they match a monitoring
        # configuration creates an event.
        from .handlers.log import LogHandler
        self.handlers.append(LogHandler(
            events=self.events,
            reread_trigger=self.reread_trigger,
            rewrite_trigger=self.rewrite_trigger,
        ))

        # this handler, when signaled, checks all configured schedules and
        # start programs as necessary.
        from .handlers.scheduler import SchedulerHandler
        self.handlers.append(SchedulerHandler(
            events=self.events,
            supervisor_server_url=supervisor_server_url,
            reread_trigger=self.reread_trigger,
            rewrite_trigger=self.rewrite_trigger,
        ))

        # start all of the handlers
        for handler in self.handlers:
            self.logger.debug("starting handler: {}".format(handler.name))
            handler.start()

        # log lines from our programs are sent to the dart-agent as events and
        # those log lines can have oddly encoded data in them. sometimes those
        # log lines contain utf8 data but sometimes they definitely do not. we
        # use stdin.buffer to get a byte stream so that we can convert this
        # data to an encoding that we like and then decide what to do with any
        # invalid data that we get: ignore it, backslash replace, etc.
        stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", newline='\n')

        # if we need to exit then this will be changed to True
        finished = False

        while (not finished and not self.killer.killed()):
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
                    # read our wrapped stdin
                    parts = self._read_message(stdin)
                    if (parts is not None):
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

            # if we decided that we're done then we are going to send a
            # message to supervisor that we're done but only if it is waiting
            # for it.
            if (needs_acknowledgement):
                # transition from READY to ACKNOWLEDGED
                # this prints to stdout where we communicate with supervisor
                print("RESULT 2\nOK", flush=True, end="")
        else:
            self.logger.info("finished supervisor listener loop")

        # tell the handlers to all stop but do it in reverse. this way the
        # event handler will start first and stop last.
        self.handlers.reverse()
        for handler in self.handlers:
            self.logger.info("stopping handler: {}".format(handler.name))
            handler.stop()

        # say goodnight, kevin.
        self.logger.info("gracefully exiting")
        return 0

    def _read_message(self, handle):
        # wait one second for a message before exiting with nothing
        while handle in select.select([handle], [], [], 1)[0]:
            # if the next line returns a false-like value then we received an
            # eof. if we have received an eof then we're going to get out
            # because something went horribly wrong.
            line = handle.readline()
            if (not line):
                raise EOFError("received eof from supervisord trying to read message header")

            # let's assume that we got a real message and it is a string
            header = dict([x.split(":") for x in line.split()])
            data_length = int(header.get("len", 0))  # this will raise a value error on bad data
            if (data_length == 0):
                return (header, None, None)

            # read in only as much data as we were told to read in
            data = handle.read(data_length)
            if (not data):
                raise EOFError("received eof from supervisord trying to read message payload")

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
        # kick off all housekeeping once per minute
        if (header["eventname"] == "TICK_60"):
            self.logger.debug("received {} event".format(header["eventname"]))
            return self._handle_tick_event(header["eventname"], event, data)

        # if it's not a tick event, send it on its way to the even thandlers
        for handler in self.handlers:
            if (handler.can_handle(header["eventname"])):
                self.logger.debug("sending {} event {} to {} handler".format(header["eventname"], header["serial"], handler.name))
                handler.handle(header["eventname"], event, data)
                self.logger.debug("{} handler finished processing {} event {}".format(handler.name, header["eventname"], header["serial"]))

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
            self.logger.warn("skipping {} from {} because it is older than {} seconds ({} seconds ago)".format(event_type, event_timestamp, interval, (timestamp - event_timestamp)))

            # don't bother checking to see if the version changed, just keep
            # processing things (including tick events) and eventually we'll
            # get to a recent tick and we'll check the whether our version has
            # changed.
            return True

        # send a keepalive to dash
        self.events.put({
            "type": "keepalive",
            "data": {
                "component": {"name": "agent"},
                "severity": 1,  # highest severity
                "timeout": 5,  # minutes
                "message": "dart agent not responding on {}".format(self.fqdn),
            }
        })

        # now that we've collapsed the tick events, issue a rewrite command
        self.logger.debug("tick handler triggering a rewrite")
        self.rewrite_trigger.set()

        # now that we've collapsed the tick events, send it to our handlers
        for handler in self.handlers:
            if (handler.can_handle(event_type)):
                handler.handle(event_type, event, data)

        # finally, we periodically check to see if we need to restart ourselves
        return not self._has_version_changed()

    def _update_system_configuration(self):
        booted = None
        try:
            import psutil
            booted = int(psutil.boot_time())
        except ModuleNotFoundError:
            pass

        # assemble all of the parts
        configuration = {
            "booted": booted,               # when the server started
            "kernel": platform.platform(),  # kernel version
        }

        # send system information to the DartAPI
        url = "{}/agent/v1/probe/{}".format(dart.agent.api.DART_API_URL, urllib.parse.quote(self.fqdn))
        response = dart.agent.api.dart.post(url, data=json.dumps(configuration), timeout=22)
        response.raise_for_status()

    def _has_version_changed(self):
        try:
            old_version = dart.agent.__version__
            importlib.reload(dart.agent)
            new_version = dart.agent.__version__

            if (old_version != new_version):
                self.logger.info("new version {} is not the same as old version {}".format(new_version, old_version))
                return True
        except Exception:
            pass

        return False
