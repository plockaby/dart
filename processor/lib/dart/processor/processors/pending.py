from . import BaseProcessor


class PendingConfigurationProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # prepare queries on start
        self.queries = {
            "select": self.session.prepare("""
                SELECT process, status
                FROM dart.configured_pending
                WHERE fqdn = ?
            """),

            "insert": self.session.prepare("""
                INSERT INTO dart.configured_pending (
                    fqdn, process, status
                ) VALUES (:fqdn, :process, :status)
                USING TIMESTAMP :timestamp
            """),

            "delete": self.session.prepare("""
                DELETE FROM dart.configured_pending
                USING TIMESTAMP :timestamp
                WHERE fqdn = :fqdn
                  AND process = :process
            """)
        }

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
        rows = self.session.execute(self.queries["select"], {"fqdn": fqdn})
        for row in rows:
            if (row["status"] in current):
                current[row["status"]].append(row["process"])

        # add the "added"
        for process in body["added"]:
            self.session.execute_async(self.queries["insert"], {
                "fqdn": fqdn,
                "process": process,
                "status": "added",
                "timestamp": int(timestamp * 1000000),
            })

        # add the "removed"
        for process in body["removed"]:
            self.session.execute_async(self.queries["insert"], {
                "fqdn": fqdn,
                "process": process,
                "status": "removed",
                "timestamp": int(timestamp * 1000000),
            })

        # add the "changed"
        for process in body["changed"]:
            self.session.execute_async(self.queries["insert"], {
                "fqdn": fqdn,
                "process": process,
                "status": "changed",
                "timestamp": int(timestamp * 1000000),
            })

        # remove the "added" that aren't there anymore
        for process in current.get("added", []):
            if (process not in body["added"]):
                self.session.execute_async(self.queries["delete"], {
                    "fqdn": fqdn,
                    "process": process,
                    "timestamp": int(timestamp * 1000000),
                })

        # remove the "removed" that aren't there anymore
        for process in current.get("removed", []):
            if (process not in body["removed"]):
                self.session.execute_async(self.queries["delete"], {
                    "fqdn": fqdn,
                    "process": process,
                    "timestamp": int(timestamp * 1000000),
                })

        # remove the "changed" that aren't there anymore
        for process in current.get("changed", []):
            if (process not in body["changed"]):
                self.session.execute_async(self.queries["delete"], {
                    "fqdn": fqdn,
                    "process": process,
                    "timestamp": int(timestamp * 1000000),
                })
