from . import BaseProcessor


class StateProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # prepare queries on start
        self.queries = {
            "insert": self.session.prepare("""
                INSERT INTO dart.configured_active (
                    fqdn, process, status, checked,
                    started, stopped, pid, exit_code, error,
                    stdout_logfile, stderr_logfile, description
                ) VALUES (
                    :fqdn, :process, :status, :checked,
                    :started, :stopped, :pid, :exit_code, :error,
                    :stdout_logfile, :stderr_logfile, :description
                )
                USING TIMESTAMP :timestamp
            """),
        }

    @property
    def name(self):
        return "state"

    # {
    #    'host': 'gp-collector-ads-01.pnw-gigapop.net',
    #    'state': {
    #        'stdout_logfile': '/data/logs/supervisor/netflow-counts-processor.log',
    #        'statename': 'RUNNING',
    #        'description': 'pid 9596, uptime 0:00:00',
    #        'stderr_logfile': '/data/logs/supervisor/netflow-counts-processor.err',
    #        'stop': 1492368547,
    #        'start': 1492368600,
    #        'name': 'netflow-counts-processor',
    #        'state': 20,
    #        'spawnerr': '',
    #        'group': 'netflow-counts-processor',
    #        'exitstatus': 0,
    #        'pid': 9596,
    #        'now': 1492368600,
    #        'logfile': '/data/logs/supervisor/netflow-counts-processor.log'
    #    },
    # }
    def process_task(self, body, message):
        # send a keepalive right off the bat
        self._send_keepalive()

        # then process the message
        state = body["state"]  # this has the details about the process in its new state
        self.logger.info("processing state change for {} on {}".format(state["name"], body["fqdn"]))

        # update cassandra with the latest state information for this process
        self.session.execute(self.queries["insert"], {
            "fqdn": body["fqdn"],
            "process": state["name"],
            "status": state["statename"],
            "checked": int(state["now"] * 1000),
            "started": int(state["start"] * 1000) if state["start"] != 0 else None,
            "stopped": int(state["stop"] * 1000) if state["stop"] != 0 else None,
            "pid": state["pid"],
            "exit_code": state["exitstatus"],
            "error": state["spawnerr"],
            "stdout_logfile": state["stdout_logfile"],
            "stderr_logfile": state["stderr_logfile"],
            "description": state["description"],
            "timestamp": int(state["now"] * 1000000),
        })
