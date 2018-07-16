from . import BaseHandler
import dart.common.event
from dart.common.supervisor import SupervisorClient
from dart.common.killer import GracefulEventKiller
from threading import Thread
import xmlrpc.client
import traceback
import platform
import psutil
import time


class ProbeHandler(BaseHandler):
    def __init__(self, queue, supervisor_server_url, configuration_file, configuration_path, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # this is the queue that will put things on the message bus
        self.queue = queue

        # keep track of where to find the supervisor socket
        self.supervisor_server_url = supervisor_server_url

        # this is where we will try to read configurations
        self.configuration_path = configuration_path
        self.configuration_file = configuration_file

        # we can set these to force a reread or a rewrite
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

        # this is the configuration that we've loaded
        self.configuration = None

    @property
    def name(self):
        return "probe"

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

        # this thread listens for the reread trigger and then probes the system
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the thread to stop using a thread safe mechanism
        self.killer.kill()

        # then wait for our thread to be finished
        self.thread.join()

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle since we can't handle anything
        pass

    # this method runs in a thread
    def _run(self):
        while (not self.killer.killed()):
            if (self.reread_trigger.wait(timeout=1)):
                try:
                    # don't just blindly load the configuration. ensure that we
                    # are able to actually load the file before replacing what
                    # we have right now.
                    configuration = self._load_configuration(self.configuration_path, self.configuration_file)
                    if (configuration is not None):
                        self.configuration = configuration
                    else:
                        self.logger.warning("{} handler not replacing a good configuration with a bad configuration".format(self.name))

                    # probe supervisor configurations
                    self._probe_active_supervisor_configurations()
                    self._probe_pending_supervisor_configurations()

                    # probe system configurations (memory, cpu, disks)
                    self._probe_system_configuration()
                except Exception as e:
                    self.logger.error("{} handler unexpected error: {}".format(self.name, repr(e)))
                    self.logger.error(traceback.format_exc())
                finally:
                    # this clears the trigger so that it can be pulled again
                    self.reread_trigger.clear()

        # tell everything that we're done
        self.logger.info("{} handler exiting".format(self.name))

    def _probe_active_supervisor_configurations(self):
        try:
            self.logger.debug("{} handler probing active supervisor configurations".format(self.name))

            # get active processes
            timestamp = time.time()
            client = SupervisorClient(self.supervisor_server_url)
            states = client.connection.supervisor.getAllProcessInfo()

            # throw the active processes onto the message bus
            self.queue.put(dict(
                exchange="active",
                payload=dict(
                    fqdn=self.fqdn,
                    timestamp=timestamp,
                    states=states,
                )
            ))

            # if there are any processes that are:
            # - being daemon monitored but not running
            # - being state monitored but are failing
            # then raise an event for that. otherwise clear any alarms.
            for state in states:
                process = state["name"]

                if (process in self.configuration["state"]):
                    configuration = self.configuration["state"][process]

                    if (state["statename"] == "RUNNING"):
                        # if the process is successfully running then clear any
                        # state alerts for it.
                        self.logger.debug("{} handler clearing state event for {} because it is now RUNNING".format(self.name, process))
                        dart.common.event.send(
                            component="dart:monitor:state:{}".format(process),
                            severity="OK",
                            subject="clear",
                        )
                    else:
                        # if this process is being state monitored and it has gone
                        # into one of these error states then raise an error.
                        if (state["statename"] in ["UNKNOWN", "FATAL", "BACKOFF"]):
                            self.logger.debug("{} handler raising state event for {} because it has gone into state {}".format(self.name, process, state["statename"]))
                            dart.common.event.send(
                                component="dart:monitor:state:{}".format(process),
                                severity=configuration["severity"],
                                contact=configuration["contact"],
                                subject="{} entered the state {}".format(process, state["statename"]),
                                message=state["spawnerr"],
                            )

                        # if this process is being state monitored and it returned
                        # an error when it exited then raise an error.
                        elif (state["spawnerr"]):
                            self.logger.debug("{} handler raising state event for {} because it exited with an error".format(self.name, process))
                            dart.common.event.send(
                                component="dart:monitor:state:{}".format(process),
                                severity=configuration["severity"],
                                contact=configuration["contact"],
                                subject="{} exited with an error".format(process),
                                message=state["spawnerr"],
                            )

                if (process in self.configuration["daemon"]):
                    configuration = self.configuration["daemon"][process]

                    if (state["statename"] == "RUNNING"):
                        self.logger.debug("{} handler clearing state event for {} because it is now RUNNING".format(self.name, process))
                        # if the process is successfully running then clear any
                        # daemon alerts for it.
                        dart.common.event.send(
                            component="dart:monitor:daemon:{}".format(process),
                            severity="OK",
                            subject="clear",
                        )
                    else:
                        self.logger.debug("{} handler raising daemon event for {} because it is in state {} when it is supposed to be in state RUNNING".format(self.name, process, state["statename"]))
                        dart.common.event.send(
                            component="dart:monitor:daemon:{}".format(process),
                            severity=configuration["severity"],
                            contact=configuration["contact"],
                            subject="{} is in state {} when it is supposed to be in state RUNNING".format(process, state["statename"]),
                        )

            # clear any error events
            dart.common.event.send(
                component="dart:agent:{}:active".format(self.name),
                severity="OK",
                subject="clear",
            )
        except xmlrpc.client.Fault as e:
            # don't want to raise any alarms about this one
            subject = "{} handler could not probe supervisor: {}".format(self.name, e.faultString)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)

            # clear any error events
            dart.common.event.send(
                component="dart:agent:{}:active".format(self.name),
                severity=2,
                subject=subject,
                message=message
            )
        except Exception as e:
            subject = "{} handler unexpected error: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # this is an unexpected error so raise a different event for it.
            # this event will not automatically clear.
            dart.common.event.send(
                component="dart:agent:{}:active:error".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )

    def _probe_pending_supervisor_configurations(self):
        try:
            self.logger.debug("{} handler probing pending supervisor configurations".format(self.name))

            # get pending process changes
            timestamp = time.time()
            client = SupervisorClient(self.supervisor_server_url)
            states = client.connection.supervisor.reloadConfig()

            # make the list easier to read. something in the supervisord
            # rpcinterface documentation about not being able to return an
            # array with a length greater than one. so this is what we get.
            pending = dict(
                added=states[0][0],
                changed=states[0][1],
                removed=states[0][2],
            )

            # throw the pending processes onto the message bus
            self.queue.put(dict(
                exchange="pending",
                payload=dict(
                    fqdn=self.fqdn,
                    timestamp=timestamp,
                    added=pending["added"],
                    removed=pending["removed"],
                    changed=pending["changed"],
                )
            ))

            # if there are any pending changes then raise an event for that
            if (len(pending["added"]) or len(pending["removed"]) or len(pending["changed"])):
                subject = []
                if (len(pending["added"])):
                    subject.append("{} added".format(",".join(pending["added"])))
                if (len(pending["removed"])):
                    subject.append("{} removed".format(",".join(pending["removed"])))
                if (len(pending["changed"])):
                    subject.append("{} changed".format(",".join(pending["changed"])))

                self.logger.debug("raising severity 3 event for {}".format("; ".join(subject)))
                dart.common.event.send(
                    component="dart:monitor:pending",
                    severity=3,
                    subject="; ".join(subject),
                )
            else:
                # clear pending change events
                dart.common.event.send(
                    component="dart:monitor:pending",
                    severity="OK",
                    subject="clear",
                )

            # clear any error events
            dart.common.event.send(
                component="dart:agent:{}:pending".format(self.name),
                severity="OK",
                subject="clear",
            )
        except xmlrpc.client.Fault as e:
            # don't want to raise any alarms about this one
            subject = "{} handler could not probe supervisor: {}".format(self.name, e.faultString)
            message = traceback.format_exc()
            self.logger.warning(subject)
            self.logger.warning(message)

            # clear any error events
            dart.common.event.send(
                component="dart:agent:{}:pending".format(self.name),
                severity=2,
                subject=subject,
                message=message
            )
        except Exception as e:
            subject = "{} handler unexpected error: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # this is an unexpected error so raise a different event for it.
            # this event will not automatically clear.
            dart.common.event.send(
                component="dart:agent:{}:pending:error".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )

    def _probe_system_configuration(self):
        try:
            self.logger.debug("{} handler probing system configuration".format(self.name))

            # when did we start probing (used by processor)
            timestamp = time.time()

            self.queue.put(dict(
                exchange="probe",
                payload=dict(
                    fqdn=self.fqdn,
                    timestamp=timestamp,
                    # this is a configuration probe
                    configuration=dict(
                        boot_time=int(psutil.boot_time()),  # when the server started
                        kernel=platform.platform(),         # kernel version
                    )
                )
            ))
        except Exception as e:
            subject = "{} handler unexpected error: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # this is an unexpected error so raise a different event for
            # it. this event will not automatically clear.
            dart.common.event.send(
                component="dart:agent:{}:configuration:error".format(self.name),
                severity=2,
                subject=subject,
                message=message,
            )
