from . import BaseProcessor


class ProbeProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # prepare queries on start
        self.queries = {
            "insert": self.session.prepare("""
                INSERT INTO dart.probe (fqdn, checked, system_started, kernel)
                VALUES (:fqdn, :checked, :system_started, :kernel)
                USING TIMESTAMP :timestamp
            """),
        }

    @property
    def name(self):
        return "probe"

    def process_task(self, body, message):
        # send a keepalive right off the bat
        self._send_keepalive()

        # then process the message
        fqdn = body["fqdn"]
        timestamp = body["timestamp"]
        self.logger.info("processing probe configurations for {}".format(fqdn))

        # did we get a host configuration probe?
        if ("configuration" in body):
            self._process_task_configuration(fqdn, timestamp, body["configuration"])

    def _process_task_configuration(self, fqdn, timestamp, probed):
        # insert the basics. one row per host.
        self.session.execute_async(self.queries["insert"], {
            "fqdn": fqdn,
            "checked": int(timestamp * 1000),
            "system_started": (probed.get("boot_time") * 1000),
            "kernel": probed.get("kernel"),
            "timestamp": int(timestamp * 1000000),
        })
