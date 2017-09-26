from . import BaseProcessor
import dart.common.event
import traceback
import cassandra
import cassandra.cluster
import cassandra.query
import time


class PendingConfigurationProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(exchange_name="pending", **kwargs)

        # the last time we sent a keepalive
        self.last_keepalive = None

    @property
    def name(self):
        return "pending"

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
        for process in configured["added"]:
            self.session.execute(insert, dict(
                fqdn=fqdn,
                process=process,
                status="added",
                timestamp=int(timestamp * 1000000),
            ))

        # add the "removed"
        for process in configured["removed"]:
            self.session.execute(insert, dict(
                fqdn=fqdn,
                process=process,
                status="removed",
                timestamp=int(timestamp * 1000000),
            ))

        # add the "changed"
        for process in configured["changed"]:
            self.session.execute(insert, dict(
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
            if (process not in configured["added"]):
                self.session.execute(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))

        # remove the "removed" that aren't there anymore
        for process in current.get("removed", []):
            if (process not in configured["removed"]):
                self.session.execute(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))

        # remove the "changed" that aren't there anymore
        for process in current.get("changed", []):
            if (process not in configured["changed"]):
                self.session.execute(delete, dict(
                    fqdn=fqdn,
                    process=process,
                    timestamp=int(timestamp * 1000000),
                ))
