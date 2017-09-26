from . import BaseProcessor
import dart.common.event
import traceback
import cassandra
import cassandra.cluster
import cassandra.query
import time


class ActiveConfigurationProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(exchange_name="active", **kwargs)

        # last time we loaded configs
        self.last_updated = None

        # the last time we sent a keepalive
        self.last_keepalive = None

        # these are the configs
        self.assignments = None
        self.monitors = None

    @property
    def name(self):
        return "active"

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

    def _process_task(self, configured):
        fqdn = configured["fqdn"]
        timestamp = configured["timestamp"]
        self.logger.info("processing active configurations for {}".format(fqdn))

        # assemble the name of the processes that we've are active on the host.
        # this set makes easier to determine what is new and what has been
        # removed.
        found = set()
        for state in configured["states"]:
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
        for state in configured["states"]:
            self.session.execute(insert, dict(
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
                self.session.execute(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))
