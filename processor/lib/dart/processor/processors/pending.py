from . import BaseProcessor
import cassandra.query


class PendingConfigurationProcessor(BaseProcessor):
    @property
    def name(self):
        return "pending"

    def process_task(self, body, message):
        # send a keepalive right off the bat
        self._send_keepalive()

        # then process the message

        fqdn = body["fqdn"]
        timestamp = body["timestamp"]
        self.logger.info("processing pending configurations for {}".format(fqdn))

        # get everything that we currently have
        current = dict(added=[], removed=[], changed=[])
        select = cassandra.query.SimpleStatement("""
            SELECT process, status
            FROM dart.configured_pending
            WHERE fqdn = %(fqdn)s
        """)
        rows = self.session.execute(select, dict(fqdn=fqdn))
        for row in rows:
            if (row["status"] in current):
                current[row["status"]].append(row["process"])

        # insert new things, update existing things
        insert = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured_pending (
                fqdn, process, status
            ) VALUES (%(fqdn)s, %(process)s, %(status)s)
            USING TIMESTAMP %(timestamp)s
        """)

        # add the "added"
        for process in body["added"]:
            self.session.execute_async(insert, dict(
                fqdn=fqdn,
                process=process,
                status="added",
                timestamp=int(timestamp * 1000000),
            ))

        # add the "removed"
        for process in body["removed"]:
            self.session.execute_async(insert, dict(
                fqdn=fqdn,
                process=process,
                status="removed",
                timestamp=int(timestamp * 1000000),
            ))

        # add the "changed"
        for process in body["changed"]:
            self.session.execute_async(insert, dict(
                fqdn=fqdn,
                process=process,
                status="changed",
                timestamp=int(timestamp * 1000000),
            ))

        # remove things that aren't there anymore
        delete = cassandra.query.SimpleStatement("""
            DELETE FROM dart.configured_pending
            USING TIMESTAMP %(timestamp)s
            WHERE fqdn = %(fqdn)s
              AND process = %(process)s
        """)

        # remove the "added" that aren't there anymore
        for process in current.get("added", []):
            if (process not in body["added"]):
                self.session.execute_async(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))

        # remove the "removed" that aren't there anymore
        for process in current.get("removed", []):
            if (process not in body["removed"]):
                self.session.execute_async(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))

        # remove the "changed" that aren't there anymore
        for process in current.get("changed", []):
            if (process not in body["changed"]):
                self.session.execute_async(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))
