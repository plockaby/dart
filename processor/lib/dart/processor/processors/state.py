from . import BaseProcessor
import dart.common.event
import traceback
import cassandra
import cassandra.cluster
import cassandra.query
import time


class StateProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(exchange_name="state", **kwargs)

        # last time we loaded configs
        self.last_updated = None

        # the last time we sent a keepalive
        self.last_keepalive = None

        # these are the configs
        self.assignments = None
        self.monitors = None

    @property
    def name(self):
        return "state"

    def process_task(self, body, msg):
        try:
            # make sure it is json that we got
            if (msg.content_type != "application/json"):
                raise ValueError("{} message is type {} and not application/json".format(self.name, msg.content_type))

            self._process_task(body)

            # raise an alarm if our event listener never processes anything
            if (self.last_keepalive is None or (int(time.time()) - 30) > self.last_keepalive):
                dart.common.event.keepalive(
                    component="dart:processor:{}".format(self.name),
                    severity=1,
                    message="dart {} processor stopped processing".format(self.name),
                    timeout=15,  # minutes
                    hostname=self.fqdn,
                )
                self.last_keepalive = int(time.time())
        except cassandra.cluster.NoHostAvailable as e:
            self.logger.warning("no cassandra hosts available: {}".format(repr(e)))
            self.logger.debug(traceback.format_exc())
        except (cassandra.OperationTimedOut, cassandra.RequestExecutionException, cassandra.InvalidRequest) as e:
            self.logger.warning("could not execute query on cassandra: {}".format(repr(e)))
            self.logger.debug(traceback.format_exc())
        except ValueError as e:
            self.logger.warning("received unparseable message: {}".format(body))
            self.logger.debug(traceback.format_exc())
        except Exception as e:
            self.logger.error("unexpected error: {}".format(repr(e)))
            self.logger.error(traceback.format_exc())
        finally:
            # always ack the message, even if we can't process it. that way we
            # don't sit there trying to parse an unparseable message forever.
            # we'll get the data eventually even if we miss a few messages
            msg.ack()

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
    def _process_task(self, event):
        state = event["state"]  # this has the details about the process in its new state
        self.logger.info("processing state change for {} on {}".format(state["name"], event["fqdn"]))

        # update cassandra with the latest state information for this process
        insert = cassandra.query.SimpleStatement("""
            INSERT INTO dart.configured_active (
                fqdn, process, status, checked,
                started, stopped, pid, exit_code, error,
                stdout_logfile, stderr_logfile, description
            ) VALUES (
                %(fqdn)s, %(process)s, %(status)s, %(checked)s,
                %(started)s, %(stopped)s, %(pid)s, %(exit_code)s, %(error)s,
                %(stdout_logfile)s, %(stderr_logfile)s, %(description)s
            )
            USING TIMESTAMP %(timestamp)s
        """)
        self.session.execute(insert, dict(
            fqdn=event["fqdn"],
            process=state["name"],
            status=state["statename"],
            checked=int(state["now"] * 1000),
            started=int(state["start"] * 1000) if state["start"] != 0 else None,
            stopped=int(state["stop"] * 1000) if state["stop"] != 0 else None,
            pid=state["pid"],
            exit_code=state["exitstatus"],
            error=state["spawnerr"],
            stdout_logfile=state["stdout_logfile"],
            stderr_logfile=state["stderr_logfile"],
            description=state["description"],
            timestamp=int(state["now"] * 1000000),
        ))
