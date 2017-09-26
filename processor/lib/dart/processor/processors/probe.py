from . import BaseProcessor
import dart.common.event
import traceback
import cassandra
import cassandra.cluster
import cassandra.query
import time


class ProbeProcessor(BaseProcessor):
    def __init__(self, **kwargs):
        super().__init__(exchange_name="probe", **kwargs)

        # the last time we sent a keepalive
        self.last_keepalive = None

    @property
    def name(self):
        return "probe"

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

    def _process_task(self, probed):
        fqdn = probed["fqdn"]
        timestamp = probed["timestamp"]
        self.logger.info("processing probe configurations for {}".format(fqdn))

        # did we get a host configuration probe?
        if ("configuration" in probed):
            self._process_task_configuration(fqdn, timestamp, probed["configuration"])

    def _process_task_configuration(self, fqdn, timestamp, probed):
        # insert the basics. one row per host.
        insert = cassandra.query.SimpleStatement("""
            INSERT INTO dart.probe (
                fqdn, checked, system_started, kernel
            ) VALUES (
                %(fqdn)s, %(checked)s, %(system_started)s, %(kernel)s
            )
            USING TIMESTAMP %(timestamp)s
        """)
        self.session.execute(insert, dict(
            fqdn=fqdn,
            checked=int(timestamp * 1000),
            system_started=(probed.get("boot_time") * 1000),
            kernel=probed.get("kernel"),
            timestamp=int(timestamp * 1000000),
        ))
