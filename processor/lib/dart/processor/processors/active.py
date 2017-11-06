from . import BaseProcessor
import cassandra.query


class ActiveConfigurationProcessor(BaseProcessor):
    @property
    def name(self):
        return "active"

    def process_task(self, body, message):
        # send a keepalive right off the bat
        self._send_keepalive()

        # then process the message
        fqdn = body["fqdn"]
        timestamp = body["timestamp"]
        self.logger.info("processing active configurations for {}".format(fqdn))

        # assemble the name of the processes that we've are active on the host.
        # this set makes easier to determine what is new and what has been
        # removed.
        found = set()
        for state in body["states"]:
            found.add(state["name"])

        # get everything that we currently have in the database.
        current = set()
        select = cassandra.query.SimpleStatement("""
            SELECT process
            FROM dart.configured_active
            WHERE fqdn = %s
        """)
        rows = self.session.execute(select, (fqdn,))
        for row in rows:
            current.add(row["process"])

        # insert new processes and update existing processes.
        insert = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured_active (
                fqdn, process, status,
                checked, started, stopped, pid, exit_code,
                stdout_logfile, stderr_logfile, error, description
            ) VALUES (
                %(fqdn)s, %(process)s, %(status)s,
                %(checked)s, %(started)s, %(stopped)s, %(pid)s, %(exit_code)s,
                %(stdout_logfile)s, %(stderr_logfile)s, %(error)s, %(description)s
            )
            USING TIMESTAMP %(timestamp)s
        """)
        for state in body["states"]:
            self.session.execute_async(insert, dict(
                fqdn=fqdn,
                process=state["name"],
                status=state["statename"],
                checked=int(timestamp * 1000),
                started=int(state["start"] * 1000) if state["start"] != 0 else None,
                stopped=int(state["stop"] * 1000) if state["stop"] != 0 else None,
                pid=state["pid"],
                exit_code=state["exitstatus"],
                stdout_logfile=state["stdout_logfile"],
                stderr_logfile=state["stderr_logfile"],
                error=state["spawnerr"],
                description=state["description"],
                timestamp=int(timestamp * 1000000),
            ))

        # remove things that aren't there anymore
        delete = cassandra.query.SimpleStatement("""
            DELETE FROM dart.configured_active
            USING TIMESTAMP %(timestamp)s
            WHERE fqdn = %(fqdn)s
              AND process = %(process)s
        """)
        for process in current:
            if (process not in found):
                self.session.execute_async(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))
