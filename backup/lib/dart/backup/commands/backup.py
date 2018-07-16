from . import BaseCommand
import cassandra.query
import json


class BackupCommand(BaseCommand):
    def run(self, **kwargs):
        export = dict()

        export["configured"] = self._export_configured()
        export["schedule"] = self._export_schedule()
        export["process_log_monitor"] = self._export_process_log_monitor()
        export["process_daemon_monitor"] = self._export_process_daemon_monitor()
        export["process_state_monitor"] = self._export_process_state_monitor()
        export["assignment"] = self._export_assignment()
        export["host_tag"] = self._export_host_tag()

        # these are only exported if we have the everything flag!
        if (kwargs.get("everything", False)):
            export["probe"] = self._export_probe()
            export["configured_active"] = self._export_configured_active()
            export["configured_pending"] = self._export_configured_pending()

        print(json.dumps(export, sort_keys=True, indent=4))
        return 0

    def _fix_timestamp(self, timestamp):
        if (timestamp is not None):
            return "{} UTC".format(timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])

    def _export_configured(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                environment,
                type,
                configuration
            FROM dart.configured
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_schedule(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                environment,
                schedule
            FROM dart.schedule
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_process_log_monitor(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                environment,
                stream,
                id,
                contact,
                name,
                regex,
                severity,
                stop
            FROM dart.process_log_monitor
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_process_daemon_monitor(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                environment,
                contact,
                severity
            FROM dart.process_daemon_monitor
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_process_state_monitor(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                process,
                environment,
                contact,
                severity
            FROM dart.process_state_monitor
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_assignment(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                process,
                environment,
                disabled
            FROM dart.assignment
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_host_tag(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                tag
            FROM dart.host_tag
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data

    def _export_probe(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                checked,
                kernel,
                system_started
            FROM dart.probe
        """)
        rows = self.session.execute(query)
        for row in rows:
            # convert datetime
            row["checked"] = self._fix_timestamp(row["checked"])
            row["system_started"] = self._fix_timestamp(row["system_started"])

            # then append the row
            data.append(row)

        return data

    def _export_configured_active(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                process,
                checked,
                description,
                error,
                exit_code,
                pid,
                started,
                status,
                stderr_logfile,
                stdout_logfile,
                stopped
            FROM dart.configured_active
        """)
        rows = self.session.execute(query)
        for row in rows:
            # convert datetime
            row["checked"] = self._fix_timestamp(row["checked"])
            row["started"] = self._fix_timestamp(row["started"])
            row["stopped"] = self._fix_timestamp(row["stopped"])

            # then append the row
            data.append(row)

        return data

    def _export_configured_pending(self):
        data = []

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                process,
                status
            FROM dart.configured_pending
        """)
        rows = self.session.execute(query)
        for row in rows:
            data.append(row)

        return data
