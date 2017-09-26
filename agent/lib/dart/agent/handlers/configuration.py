from . import BaseHandler
import dart.common.event
import dart.common.database
from dart.common.killer import GracefulEventKiller
import logging
import traceback
from threading import Thread
import cassandra
import cassandra.cluster
import cassandra.query
import json
import os


class ConfigurationHandler(BaseHandler):
    def __init__(self, configuration_path, supervisor_configuration_file, scheduler_configuration_file, monitor_configuration_file, reread_trigger, rewrite_trigger, **kwargs):
        super().__init__(**kwargs)

        # ignore cassandra errors only if we aren't explicitly in verbose mode
        if (not self.logger.isEnabledFor(logging.DEBUG)):
            logging.getLogger("cassandra").setLevel(logging.ERROR)

        # we can set these to force a reread or a rewrite
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger

        # this is where we will try to write configurations
        self.configuration_path = configuration_path
        self.supervisor_configuration_file = supervisor_configuration_file
        self.scheduler_configuration_file = scheduler_configuration_file
        self.monitor_configuration_file = monitor_configuration_file

        # this is how we will trigger the thread so that it knows to exit
        self.killer = GracefulEventKiller()

    @property
    def name(self):
        return "configuration"

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle since we can't handle anything
        pass

    def start(self):
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # trigger the event using a thread safe mechanism
        self.killer.kill()

        # then wait for our thread to be finished
        self.thread.join()

    # this method runs inside of a thread
    def _run(self):
        try:
            # get a cassandra session. if we can't get a session then this will
            # return None. we normally shouldn't ever die here because the
            # session handler tries REALLY hard to get a session. the ONLY
            # reason we might not get a connection thus getting None rather
            # than exception is if a signal to kill were sent while trying.
            session = dart.common.database.session(killer=self.killer)
            if (session is None):
                raise RuntimeError("could not get connection to cassandra")

            # make our session usable by the other parts of our handler
            self.session = session

            # if we haven't received a kill signal, wait for a trigger telling
            # us to rewrite our configurations. that trigger is set every sixty
            # seconds by TICK events or when we receive a message from the
            # coordinator queue.
            while (not self.killer.killed()):
                if (self.rewrite_trigger.wait(timeout=1)):
                    try:
                        assignments = self._get_assignments()
                        configurations = self._get_configurations(assignments)
                        schedules = self._get_schedules(assignments)
                        monitors = self._get_monitors(assignments)

                        # now write the configurations to disk
                        self._write_supervisor_configurations(configurations, self.configuration_path, self.supervisor_configuration_file)
                        self._write_scheduler_configurations(schedules, self.configuration_path, self.scheduler_configuration_file)
                        self._write_monitor_configurations(monitors, self.configuration_path, self.monitor_configuration_file)

                        # clear the transient error events
                        dart.common.event.send(
                            component="dart:agent:{}".format(self.name),
                            severity=6,
                            subject="clear",
                        )
                    except cassandra.cluster.NoHostAvailable as e:
                        subject = "{} handler found no cassandra hosts available: {}".format(self.name, repr(e))
                        message = traceback.format_exc()
                        self.logger.warning(subject)
                        self.logger.warning(message)

                        # this is a data source error but we don't want an incident
                        # for it. this event will clear automatically the next time
                        # we successfuly write configurations.
                        dart.common.event.send(
                            component="dart:agent:{}".format(self.name),
                            severity=3,
                            subject=subject,
                            message=message,
                        )
                    except (cassandra.OperationTimedOut, cassandra.RequestExecutionException, cassandra.InvalidRequest) as e:
                        subject = "{} handler could not execute query on cassandra: {}".format(self.name, repr(e))
                        message = traceback.format_exc()
                        self.logger.warning(subject)
                        self.logger.warning(message)

                        # this is a data source error but we don't want an incident
                        # for it. this event will clear automatically the next time
                        # we successfully write configurations.
                        dart.common.event.send(
                            component="dart:agent:{}".format(self.name),
                            severity=3,
                            subject=subject,
                            message=message,
                        )
                    except OSError as e:
                        subject = "{} handler could not write configuration files: {}".format(self.name, repr(e))
                        message = traceback.format_exc()
                        self.logger.warning(subject)
                        self.logger.warning(message)

                        # this is a system error, create a non-escalating incident.
                        # this event will automatically clear if we are able to
                        # successfully write our configurations.
                        dart.common.event.send(
                            component="dart:agent:{}".format(self.name),
                            severity=2,
                            subject=subject,
                            message=message,
                        )
                    except Exception as e:
                        subject = "{} handler unexpected error: {}".format(self.name, repr(e))
                        message = traceback.format_exc()
                        self.logger.error(subject)
                        self.logger.error(message)

                        # problems that we didn't expect should create
                        # non-escalating incidents. this event will not clear
                        # automatically.
                        dart.common.event.send(
                            component="dart:agent:{}:error".format(self.name),
                            severity=2,
                            subject=subject,
                            message=message,
                        )
                    finally:
                        # this clears the trigger so that it can be set again
                        self.rewrite_trigger.clear()

                        # now trigger a reread to pick up the configurations that
                        # just finished writing. if the trigger is already set then
                        # we will wait before trying to set it again.
                        self.logger.info("{} handler triggering a reread".format(self.name))
                        self.reread_trigger.set()
        except Exception as e:
            subject = "{} handler unexpected error launching agent: {}".format(self.name, repr(e))
            message = traceback.format_exc()
            self.logger.error(subject)
            self.logger.error(message)

            # we should only end up in here if something went really terribly
            # wrong setting up the handler. we should raise a high severity to
            # get dart restarted.
            dart.common.event.send(
                component="dart:agent:{}:error".format(self.name),
                severity=1,
                subject=subject,
                message=message,
            )

        # tell everything that we're done
        self.logger.info("{} handler exiting".format(self.name))

    def _get_assignments(self):
        assignments = {}
        query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                environment,
                disabled
            FROM dart.assignment
            WHERE fqdn = %s
        """)
        rows = self.session.execute(query, (self.fqdn,))
        for row in rows:
            assignments[row["process"]] = {
                "process": row["process"],
                "environment": row["environment"],
                "disabled": row["disabled"],
            }

        return assignments

    def _get_configurations(self, assignments):
        configurations = {}

        futures = []
        future_query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                configuration
            FROM dart.configured
            WHERE process = %s
              AND environment = %s
        """)
        for process in assignments:
            futures.append(self.session.execute_async(future_query, [process, assignments[process]["environment"]]))

        for future in futures:
            rows = future.result()
            for row in rows:
                # ignore empty configurations
                if (row["configuration"]):
                    configurations[row["process"]] = row["configuration"]

        return configurations

    def _get_schedules(self, assignments):
        schedules = {}

        futures = []
        future_query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                schedule
            FROM dart.schedule
            WHERE process = %s
              AND environment = %s
        """)
        for process in assignments:
            # don't schedule processes that are disabled
            if (not assignments[process]["disabled"]):
                futures.append(self.session.execute_async(future_query, [process, assignments[process]["environment"]]))

        for future in futures:
            rows = future.result()
            for row in rows:
                # ignore any empty schedules
                if (row["schedule"]):
                    schedules[row["process"]] = row["schedule"]

        return schedules

    def _get_monitors(self, assignments):
        monitors = {}

        # get state monitors
        futures = []
        future_query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                contact,
                severity
            FROM dart.process_state_monitor
            WHERE process = %s
              AND environment = %s
        """)
        for process in assignments:
            # don't monitor processes that are disabled
            if (not assignments[process]["disabled"]):
                futures.append(self.session.execute_async(future_query, [process, assignments[process]["environment"]]))

        monitors["state"] = {}
        for future in futures:
            rows = future.result()
            for row in rows:
                monitors["state"][row["process"]] = row

        # get daemon monitors
        futures = []
        future_query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                contact,
                severity
            FROM dart.process_daemon_monitor
            WHERE process = %s
              AND environment = %s
        """)
        for process in assignments:
            # don't monitor processes that are disabled
            if (not assignments[process]["disabled"]):
                futures.append(self.session.execute_async(future_query, [process, assignments[process]["environment"]]))

        monitors["daemon"] = {}
        for future in futures:
            rows = future.result()
            for row in rows:
                monitors["daemon"][row["process"]] = row

        # get log monitors
        futures = []
        future_query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                id,
                stream,
                regex,
                name,
                stop,
                contact,
                severity
            FROM dart.process_log_monitor
            WHERE process = %s
              AND environment = %s
              AND stream = %s
            ORDER BY id
        """)
        for process in assignments:
            # don't monitor processes that are disabled
            if (not assignments[process]["disabled"]):
                for stream in ["stderr", "stdout"]:
                    futures.append(self.session.execute_async(future_query, [process, assignments[process]["environment"], stream]))

        # the log monitor has stdout and stderr monitors
        monitors["log"] = {"stdout": {}, "stderr": {}}
        for future in futures:
            rows = future.result()
            for row in rows:
                if (row["process"] not in monitors["log"][row["stream"]]):
                    monitors["log"][row["stream"]][row["process"]] = []
                monitors["log"][row["stream"]][row["process"]].append({
                    "regex": row["regex"],
                    "name": row["name"],
                    "stop": row["stop"],
                    "contact": row["contact"],
                    "severity": row["severity"],
                })

        return monitors

    def _write_supervisor_configurations(self, configurations, path_name, file_name):
        # take the configurations and write them to a file that supervisord
        # will read. we're going to write a temporary file and then replace the
        # existing file with the temporary file.
        path = "{}/{}".format(path_name, file_name)
        temporary_path = "{}/.{}.tmp".format(path_name, file_name)
        self.logger.info("{} handler writing new supervisor configuration file: {}".format(self.name, temporary_path))
        with open(temporary_path, "w") as f:
            for key in sorted(configurations):
                value = configurations[key]
                print("[program:{}]".format(key), file=f)
                print(value, file=f)

        # move temp file into place. the os.replace function is atomic so
        # we can be sure that nothing will read an empty file while we move
        # the new one into place
        self.logger.info("{} handler moving {} to {}".format(self.name, temporary_path, path))
        os.replace(temporary_path, path)

    def _write_scheduler_configurations(self, configurations, path_name, file_name):
        # take the configurations and write them to a file that the scheduler
        # will read. we're going to write a temporary file and then replace the
        # existing file with the temporary file.
        path = "{}/{}".format(path_name, file_name)
        temporary_path = "{}/.{}.tmp".format(path_name, file_name)
        self.logger.info("{} handler writing new scheduler configuration file: {}".format(self.name, temporary_path))
        with open(temporary_path, "w") as f:
            json.dump(configurations, f, sort_keys=True, indent=4)

        # move temp file into place. the os.replace function is atomic so
        # we can be sure that nothing will read an empty file while we move
        # the new one into place
        self.logger.info("{} handler moving {} to {}".format(self.name, temporary_path, path))
        os.replace(temporary_path, path)

    def _write_monitor_configurations(self, configurations, path_name, file_name):
        # take the configurations and write them to a file that the monitor
        # will read. we're going to write a temporary file and then replace the
        # existing file with the temporary file.
        path = "{}/{}".format(path_name, file_name)
        temporary_path = "{}/.{}.tmp".format(path_name, file_name)
        self.logger.info("{} handler writing new monitor configuration file: {}".format(self.name, temporary_path))
        with open(temporary_path, "w") as f:
            json.dump(configurations, f, sort_keys=True, indent=4)

        # move temp file into place. the os.replace function is atomic so
        # we can be sure that nothing will read an empty file while we move
        # the new one into place
        self.logger.info("{} handler moving {} to {}".format(self.name, temporary_path, path))
        os.replace(temporary_path, path)
