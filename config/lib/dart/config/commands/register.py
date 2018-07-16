from . import BaseCommand
import sys
import yaml
import cassandra.query
import traceback
from crontab import CronTab
import re


class RegisterCommand(BaseCommand):
    def run(self, file, **kwargs):
        self.logger.info("processing {} for registration with dart".format(file))
        data = None

        try:
            if (file == "-"):
                data = yaml.load(sys.stdin.read())
            else:
                with open(file, "r") as f:
                    data = yaml.load(f.read())
        except OSError as e:
            self.logger.error("could not load {}: {}".format(file, e))
        except UnicodeDecodeError as e:
            self.logger.error("could not load {}: {}".format(file, e))
        except yaml.YAMLError as e:
            self.logger.error("could not load {}: {}".format(file, e))
        except Exception as e:
            self.logger.error(traceback.format_exc())

        if (data is None):
            self.logger.error("found no valid registration data in {}".format(file))
            raise RuntimeError("invalid dartrc file")

        # check to see if we have a process list
        processes = data.get("processes")

        # if we don't ahve processes then we're going to skip everything else
        if (processes is None):
            self.logger.info("no processes found -- skipping processes registration")
        else:
            if (not isinstance(processes, list)):
                raise RuntimeError("invalid dartrc file: processes is not a list")

            # this will return a slightly modified version with the environment
            # key validated and updated. we will use that to do our auditing.
            processes = self._register(processes)

    def _register(self, processes):
        # these are the names of the processes and environments that we've found
        # in this configuration file. the environments is keyed by process and
        # the value is an array of environments for that process.
        names = set()
        environments = dict()

        # validate that we have a name and environment for each one
        for index, process in enumerate(processes):
            name = process.get("name")
            if (not name):
                raise RuntimeError("invalid dartrc file: process {} has no name".format(index))

            environment = process.get("environment", "production")
            if (not environment):
                raise RuntimeError("invalid dartrc file: process {} has no environment name".format(name))

            # this process is at least somewhat valid!
            self.logger.info("found process named {} in {}".format(name, environment))

            process["environment"] = environment
            names.add(name)
            if (name not in environments):
                environments[name] = set()
            environments[name].add(environment)

        # get the list of assignments for each process. if an environment
        # for a process has disappeared then we stop the registration and
        # return an error. we don't want to remove an environment that is
        # currently in use.
        for name in names:
            # these are all of the environments that this process is assigned
            # to. it's a dict whose key is the name of the environment and the
            # value is a set of fqdns that environment is assigned to.
            assignments = self._get_assigned_environments(name)
            for environment in assignments:
                if (environment not in environments[name]):
                    raise RuntimeError("invalid dartrc file: cannot remove environment '{}' from '{}' when it is assigned to {}".format(environment, name, ", ".join(assignments[environment])))

        # go through the processes/environments that we just received in the
        # configuration file and insert the changes (including deletions of
        # individual sections) to each of these:
        # - supervisor
        # - schedule
        # - monitoring (daemon, state, log)
        for process in processes:
            # the primary keys for doing the updating
            name = process.get("name")
            environment = process.get("environment")

            # the type can be either "program" or "eventlistener" but the
            # default is "program".
            type = process.get("type", "program")

            if (type not in ("program", "eventlistener")):
                raise RuntimeError("invalid dartrc file: process type for '{}' in '{}' must be either 'program' or 'eventlistener' and not '{}'".format(name, environment, type))

            # the process values that we're going to update
            supervisor = process.get("supervisor", "").strip()
            schedule = process.get("schedule", "").strip()
            monitors = process.get("monitoring", dict())
            daemon_monitor = monitors.get("daemon")
            state_monitor = monitors.get("state")
            log_monitor = monitors.get("logs")

            if (supervisor):
                self.logger.info("adding supervisor configuration for {} '{}' in '{}'".format(type, name, environment))
                self._insert_supervisor_environment(type, name, environment, supervisor)
            else:
                self.logger.info("removing supervisor configuration for '{}' in '{}'".format(name, environment))
                self._remove_supervisor_environment(name, environment)

            if (schedule):
                self.logger.info("adding schedule for '{}' in '{}'".format(name, environment))
                self._insert_schedule_environment(name, environment, schedule)
            else:
                self.logger.info("removing schedule for '{}' in '{}'".format(name, environment))
                self._remove_schedule_environment(name, environment)

            if (daemon_monitor):
                self.logger.info("adding daemon monitors for '{}' in '{}'".format(name, environment))
                self._insert_process_daemon_monitor_environment(name, environment, daemon_monitor)
            else:
                self.logger.info("removing daemon monitors for '{}' in '{}'".format(name, environment))
                self._remove_process_daemon_monitor_environment(name, environment)

            if (state_monitor):
                self.logger.info("adding state monitors for '{}' in '{}'".format(name, environment))
                self._insert_process_state_monitor_environment(name, environment, state_monitor)
            else:
                self.logger.info("removing state monitors for '{}' in '{}'".format(name, environment))
                self._remove_process_state_monitor_environment(name, environment)

            if (log_monitor):
                self.logger.info("adding log monitors for '{}' in '{}'".format(name, environment))
                self._insert_process_log_monitor_environment(name, environment, log_monitor)
            else:
                self.logger.info("removing log monitors for '{}' in '{}'".format(name, environment))
                self._remove_process_log_monitor_environment(name, environment)

        # go through the each of these and find what is currently configured
        # and delete any environments that we didn't just receive in the
        # configuration file:
        # - supervisor
        # - schedule
        # - monitoring (daemon, state, log)
        for name in names:
            configured = self._get_supervisor_environments(name)
            for environment in configured:
                if (environment not in environments[name]):
                    self.logger.info("removing supervisor configuration for environment '{}' for process '{}'".format(environment, name))
                    self._remove_supervisor_environment(name, environment)

            configured = self._get_schedule_environments(name)
            for environment in configured:
                if (environment not in environments[name]):
                    self.logger.info("removing schedule configuration for environment '{}' for process '{}'".format(environment, name))
                    self._remove_schedule_environment(name, environment)

            configured = self._get_process_daemon_monitor_environments(name)
            for environment in configured:
                if (environment not in environments[name]):
                    self.logger.info("removing daemon monitor configuration for environment '{}' for process '{}'".format(environment, name))
                    self._remove_process_daemon_monitor_environment(name, environment)

            configured = self._get_process_state_monitor_environments(name)
            for environment in configured:
                if (environment not in environments[name]):
                    self.logger.info("removing state monitor configuration for environment '{}' for process '{}'".format(environment, name))
                    self._remove_process_state_monitor_environment(name, environment)

            configured = self._get_process_log_monitor_environments(name)
            for environment in configured:
                if (environment not in environments[name]):
                    self.logger.info("removing log monitor configuration for environment '{}' for process '{}'".format(environment, name))
                    self._remove_process_log_monitor_environment(name, environment)

        return processes

    def _get_assigned_environments(self, process):
        results = dict()

        query = cassandra.query.SimpleStatement("""
            SELECT fqdn, environment
            FROM dart.assignment
            WHERE process = %s
        """)
        rows = self.session.execute(query, (process,))
        for row in rows:
            if (row["environment"] not in results):
                results[row["environment"]] = set()
            results[row["environment"]].add(row["fqdn"])

        return results

    def _get_supervisor_environments(self, process):
        results = set()

        query = cassandra.query.SimpleStatement("""
            SELECT environment
            FROM dart.configured
            WHERE process = %s
        """)
        rows = self.session.execute(query, (process,))
        for row in rows:
            results.add(row["environment"])

        return results

    def _get_schedule_environments(self, process):
        results = set()

        query = cassandra.query.SimpleStatement("""
            SELECT environment
            FROM dart.schedule
            WHERE process = %s
        """)
        rows = self.session.execute(query, (process,))
        for row in rows:
            results.add(row["environment"])

        return results

    def _get_process_daemon_monitor_environments(self, process):
        results = set()

        query = cassandra.query.SimpleStatement("""
            SELECT environment
            FROM dart.process_daemon_monitor
            WHERE process = %s
        """)
        rows = self.session.execute(query, (process,))
        for row in rows:
            results.add(row["environment"])

        return results

    def _get_process_state_monitor_environments(self, process):
        results = set()

        query = cassandra.query.SimpleStatement("""
            SELECT environment
            FROM dart.process_state_monitor
            WHERE process = %s
        """)
        rows = self.session.execute(query, (process,))
        for row in rows:
            results.add(row["environment"])

        return results

    def _get_process_log_monitor_environments(self, process):
        results = set()

        query = cassandra.query.SimpleStatement("""
            SELECT environment
            FROM dart.process_log_monitor
            WHERE process = %s
            ALLOW FILTERING
        """)
        rows = self.session.execute(query, (process,))
        for row in rows:
            results.add(row["environment"])

        return results

    def _remove_supervisor_environment(self, process, environment):
        query = cassandra.query.SimpleStatement("""
            DELETE FROM dart.configured
            WHERE process = %s
              AND environment = %s
        """)
        self.session.execute(query, (process, environment))

    def _remove_schedule_environment(self, process, environment):
        query = cassandra.query.SimpleStatement("""
            DELETE FROM dart.schedule
            WHERE process = %s
              AND environment = %s
        """)
        self.session.execute(query, (process, environment))

    def _remove_process_daemon_monitor_environment(self, process, environment):
        query = cassandra.query.SimpleStatement("""
            DELETE FROM dart.process_daemon_monitor
            WHERE process = %s
              AND environment = %s
        """)
        self.session.execute(query, (process, environment))

    def _remove_process_state_monitor_environment(self, process, environment):
        query = cassandra.query.SimpleStatement("""
            DELETE FROM dart.process_state_monitor
            WHERE process = %s
              AND environment = %s
        """)
        self.session.execute(query, (process, environment))

    def _remove_process_log_monitor_environment(self, process, environment, streams=["stdout", "stderr"]):
        for stream in streams:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.process_log_monitor
                WHERE process = %s
                  AND environment = %s
                  AND stream = %s
            """)
            self.session.execute(query, (process, environment, stream))

    def _insert_supervisor_environment(self, type, process, environment, configuration):
        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured (process, environment, type, configuration)
            VALUES (%s, %s, %s, %s)
        """)
        self.session.execute(query, (process, environment, type, configuration))

    def _insert_schedule_environment(self, process, environment, configuration):
        # validate the schedule first
        try:
            CronTab(configuration)
        except ValueError as e:
            raise RuntimeError("invalid dartrc file: schedule '{}' for '{}' in '{}' is invalid".format(configuration, process, environment))

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.schedule (process, environment, schedule)
            VALUES (%s, %s, %s)
        """)
        self.session.execute(query, (process, environment, configuration))

    def _insert_process_daemon_monitor_environment(self, process, environment, configuration):
        contact = configuration.get("contact")

        # severity can be 1, 2, 3, 4, 5 or "OK"
        severity = configuration.get("severity")
        if (severity is None):
            raise RuntimeError("invalid dartrc file: daemon severity is missing for '{}' in '{}'".format(process, environment))
        if (severity != str(severity)):
            try:
                severity = int(severity)
            except TypeError as e:
                raise RuntimeError("invalid dartrc file: daemon severity '{}' for '{}' in '{}' is invalid".format(severity, process, environment))
        severity = str(severity).strip().upper()
        if (severity not in ["1", "2", "3", "4", "5", "OK"]):
            raise RuntimeError("invalid dartrc file: daemon severity '{}' for '{}' in '{}' is invalid".format(severity, process, environment))

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.process_daemon_monitor (process, environment, contact, severity)
            VALUES (%s, %s, %s, %s)
        """)
        self.session.execute(query, (process, environment, contact, severity))

    def _insert_process_state_monitor_environment(self, process, environment, configuration):
        contact = configuration.get("contact")

        # severity can be 1, 2, 3, 4, 5 or "OK"
        severity = configuration.get("severity")
        if (severity is None):
            raise RuntimeError("invalid dartrc file: state severity is missing for '{}' in '{}'".format(process, environment))
        if (severity != str(severity)):
            try:
                severity = int(severity)
            except TypeError as e:
                raise RuntimeError("invalid dartrc file: state severity '{}' for '{}' in '{}' is invalid".format(severity, process, environment))
        severity = str(severity).strip().upper()
        if (severity not in ["1", "2", "3", "4", "5", "OK"]):
            raise RuntimeError("invalid dartrc file: state severity '{}' for '{}' in '{}' is invalid".format(severity, process, environment))

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.process_state_monitor (process, environment, contact, severity)
            VALUES (%s, %s, %s, %s)
        """)
        self.session.execute(query, (process, environment, contact, severity))

    def _insert_process_log_monitor_environment(self, process, environment, configurations):
        if (not isinstance(configurations, dict)):
            raise RuntimeError("invalid dartrc file: log monitors for '{}' in '{}' must contain only the keys 'stdout' and 'stderr'".format(process, environment))
        for stream in configurations:
            if (stream not in ["stdout", "stderr"]):
                raise RuntimeError("invalid dartrc file: log monitors for '{}' in '{}' must contain only the keys 'stdout' and 'stderr': invalid stream '{}'".format(process, environment, stream))

        stdout_configurations = configurations.get("stdout")
        if (stdout_configurations is not None):
            self.__insert_process_log_monitor_environment(process, environment, "stdout", stdout_configurations)
        else:
            self._remove_process_log_monitor_environment(process, environment, ["stdout"])

        stderr_configurations = configurations.get("stderr")
        if (stderr_configurations is not None):
            self.__insert_process_log_monitor_environment(process, environment, "stderr", stderr_configurations)
        else:
            self._remove_process_log_monitor_environment(process, environment, ["stderr"])

    def __insert_process_log_monitor_environment(self, process, environment, stream, configuration):
        validated = []

        # validate the log monitors first
        for index, config in enumerate(configuration):
            regex = config.get("regex")  # must exist
            name = config.get("name")  # optional
            severity = config.get("severity")  # optional but must be int
            stop = config.get("stop")  # optional but must be a boolean
            contact = config.get("contact")  # optional

            # validate the regex: must exist, must be valid
            if (regex is None):
                raise RuntimeError("invalid dartrc file: regex missing for '{}' monitor '{}' for '{}' in '{}'".format(stream, index, process, environment))
            try:
                re.compile(regex)
            except re.error as e:
                raise RuntimeError("invalid dartrc file: '{}' monitor '{}' for '{}' in '{}' does not compile: '{}'".format(stream, index, process, environment, e))

            # severity can be 1, 2, 3, 4, 5 or "OK"
            if (severity is not None):
                if (severity != str(severity)):
                    try:
                        severity = int(severity)
                    except TypeError as e:
                        raise RuntimeError("invalid dartrc file: severity for '{}' monitor '{}' for '{}' in '{}' is invalid: '{}'".format(stream, index, process, environment, severity))
                severity = str(severity).strip().upper()
                if (severity not in ["1", "2", "3", "4", "5", "OK"]):
                    raise RuntimeError("invalid dartrc file: severity for '{}' monitor '{}' for '{}' in '{}' is invalid: '{}'".format(stream, index, process, environment, severity))

            # validate the stop
            if (stop is not None):
                if (str(stop).lower() in ['yes', 'true', 'on', '1']):
                    stop = True
                else:
                    stop = False
            else:
                stop = False

            validated.append(dict(
                regex=regex,
                name=name,
                severity=severity,
                stop=stop,
                contact=contact,
            ))

        query = cassandra.query.SimpleStatement("""
            DELETE FROM dart.process_log_monitor
            WHERE process = %s
              AND environment = %s
              AND stream = %s
        """)
        self.session.execute(query, (process, environment, stream))

        for index, valid in enumerate(validated):
            query = cassandra.query.SimpleStatement("""
                INSERT INTO dart.process_log_monitor (process, environment, stream, id, regex, name, contact, severity, stop)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """)
            self.session.execute(query, (process, environment, stream, index, valid["regex"], valid["name"], valid["contact"], valid["severity"], valid["stop"]))
