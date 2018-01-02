import logging
import kombu
import kombu.pools
import random
import dart.common.configuration


logger = logging.getLogger(__name__)


def command(fqdn, action, process=None):
    # NOTE!!!
    # do NOT put checks against cassandra in here for valid fully qualified
    # domain names and valid process names. if the fully qualified domain name
    # is not the name of a valid host then the message will disappear into the
    # exchange never to come back out. if the process is invalid then the host
    # will ignore the message. if you REALLY want to avoid sending invalid
    # messages then you are free to check for valid fully qualified domain name
    # and processes before calling this method. the goal here is to not require
    # a connection to cassandra just to send a quick message to a host.

    # get a url but randomize it somewhat so that every server
    # isn't connecting to the same instance of rabbitmq.
    configuration = dart.common.configuration.load()
    urls = configuration["rabbitmq"]["urls"]
    connection = kombu.Connection(";".join(random.sample(urls, len(urls))))

    # send the command to the coordinator exchange
    exchange = kombu.Exchange("coordinator", type="direct")

    if (process is None):
        logger.debug("connected to message bus, sending {} on {}".format(action, process, fqdn))
        with kombu.pools.producers[connection].acquire(block=True) as producer:
            producer.publish(
                dict(action=action),
                routing_key=fqdn,
                exchange=exchange,
                declare=[exchange],
            )
    else:
        logger.debug("connected to message bus, sending {} to {} on {}".format(action, process, fqdn))
        with kombu.pools.producers[connection].acquire(block=True) as producer:
            producer.publish(
                dict(action=action, process=process),
                routing_key=fqdn,
                exchange=exchange,
                declare=[exchange],
            )
