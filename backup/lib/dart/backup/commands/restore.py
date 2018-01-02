from . import BaseCommand
import sys
import json
import cassandra.query
import traceback


class RestoreCommand(BaseCommand):
    def run(self, file, **kwargs):
        self.logger.info("processing {} for registration with dart".format(file))
        data = None

        try:
            if (file == "-"):
                data = json.load(sys.stdin)
            else:
                with open(file, "r") as f:
                    data = json.load(f)
        except OSError as e:
            self.logger.error("could not load {}: {}".format(file, e))
        except UnicodeDecodeError as e:
            self.logger.error("could not load {}: {}".format(file, e))
        except ValueError as e:
            self.logger.error("could not load {}: {}".format(file, e))
        except Exception as e:
            self.logger.error(traceback.format_exc())

        if (data is None):
            self.logger.error("found no valid configurations in {}".format(file))
            raise RuntimeError("invalid backup file")

        # are we cleaning out the tables before we begin?
        truncate = kwargs.get("truncate", False)

        if (not kwargs.get("do_not_ask", False)):
            if (not self._ask("You are restoring the database. Are you sure that you want to continue?")):
                return
            if (truncate):
                if (not self._ask("You have asked to truncate all tables before beginning. Are you sure that you want to REMOVE ALL DATA?")):
                    return

        if (truncate):
            self.logger.warning("truncating tables before loading new data")

        if ("configured" in data):
            self.logger.info("importing configured data")
            self._import_configured(data.get("configured"), truncate=truncate)

        if ("schedule" in data):
            self.logger.info("importing schedule data")
            self._import_schedule(data.get("schedule"), truncate=truncate)

        if ("process_log_monitor" in data):
            self.logger.info("importing process log monitor data")
            self._import_process_log_monitor(data.get("process_log_monitor"), truncate=truncate)

        if ("process_daemon_monitor" in data):
            self.logger.info("importing process daemon monitor data")
            self._import_process_daemon_monitor(data.get("process_daemon_monitor"), truncate=truncate)

        if ("process_state_monitor" in data):
            self.logger.info("importing process state monitor data")
            self._import_process_state_monitor(data.get("process_state_monitor"), truncate=truncate)

        if ("assignment" in data):
            self.logger.info("importing assignment data")
            self._import_assignment(data.get("assignment"), truncate=truncate)

        if ("host_tag" in data):
            self.logger.info("importing host tag data")
            self._import_host_tag(data.get("host_tag"), truncate=truncate)

        if ("probe" in data):
            self.logger.info("importing probe data")
            self._import_(data.get("probe"), truncate=truncate)

        if ("configured_active" in data):
            self.logger.info("importing configured active data")
            self._import_(data.get("configured_active"), truncate=truncate)

        if ("configured_pending" in data):
            self.logger.info("importing configured pending data")
            self._import_(data.get("configured_pending"), truncate=truncate)

    def _ask(self, question):
        answer = None
        while (not answer):
            answer = input("{} [y/n] ".format(question)).strip().lower()
            if (answer not in ["y", "n"]):
                answer = None
            else:
                return (answer == "y")

    def _import_configured(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.configured
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured (process, environment, configuration)
            VALUES (%(process)s, %(environment)s, %(configuration)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_schedule(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.schedule
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.schedule (process, environment, schedule)
            VALUES (%(process)s, %(environment)s, %(schedule)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_process_log_monitor(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.process_log_monitor
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.process_log_monitor (process, environment, stream, id, contact, name, regex, severity, stop)
            VALUES (%(process)s, %(environment)s, %(stream)s, %(id)s, %(contact)s, %(name)s, %(regex)s, %(severity)s, %(stop)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_process_daemon_monitor(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.process_daemon_monitor
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.process_daemon_monitor (process, environment, contact, severity)
            VALUES (%(process)s, %(environment)s, %(contact)s, %(severity)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_process_state_monitor(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.process_state_monitor
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.process_state_monitor (process, environment, contact, severity)
            VALUES (%(process)s, %(environment)s, %(contact)s, %(severity)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_assignment(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.assignment
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.assignment (fqdn, process, environment, disabled)
            VALUES (%(fqdn)s, %(process)s, %(environment)s, %(disabled)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_host_tag(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.host_tag
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.host_tag (fqdn, tag)
            VALUES (%(fqdn)s, %(tag)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_probe(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.probe
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.probe (fqdn, checked, kernel, system_started)
            VALUES (%(fqdn)s, %(checked)s, %(kernel)s, %(system_started)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_configured_active(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.configured_active
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured_active (fqdn, process, checked, description, error, exit_code, pid, started, status, stderr_logfile, stdout_logfile, stopped)
            VALUES (%(fqdn)s, %(process)s, %(checked)s, %(description)s, %(error)s, %(exit_code)s, %(pid)s, %(started)s, %(status)s, %(stderr_logfile)s, %(stdout_logfile)s, %(stopped)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)

    def _import_configured_pending(self, data, truncate=False):
        if (truncate):
            query = cassandra.query.SimpleStatement("""
                TRUNCATE TABLE dart.configured_pending
            """)
            self.session.execute(query)

        query = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured_pending (fqdn, process, status)
            VALUES (%(fqdn)s, %(process)s, %(status)s)
        """)
        for datum in data:
            self.logger.debug(datum)
            self.session.execute(query, datum)
