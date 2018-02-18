import logging
import traceback
import kombu
import kombu.pools
import amqp.exceptions
import random
import socket
import dart.common.configuration


def command(fqdn, action, process=None, retries=None):
    logger = logging.getLogger(__name__)

    try:
        # NOTE!!!
        # do NOT put checks against cassandra in here for valid fully qualified
        # domain names and valid process names. if the fully qualified domain
        # name is not the name of a valid host then the message will disappear
        # into the exchange never to come back out. if the process is invalid
        # then the host will ignore the message. if you REALLY want to avoid
        # sending invalid messages then you are free to check for valid fully
        # qualified domain name and processes before calling this method. the
        # goal here is to not require a connection to cassandra just to send a
        # quick message to a host.

        # generate the url out here so that it is randomized in the same way.
        # we randomize it so that all clients aren't connecting to the same
        # instance every time. but we want to randomize it once so that we
        # don't create a new pool on every connection failure.
        configuration = dart.common.configuration.load()
        urls = configuration["rabbitmq"]["urls"]
        username = configuration["rabbitmq"]["username"]
        password = configuration["rabbitmq"]["password"]
        url = ";".join(random.sample(urls, len(urls))).format(username=username, password=password)

        # this will try ten times to get a connection
        with kombu.Connection(url).ensure_connection(max_retries=retries) as connection:
            with kombu.Producer(connection) as producer:
                # send the command to the coordinator exchange
                exchange = kombu.Exchange("coordinator", type="direct")

                if (process is None):
                    logger.debug("connected to message bus, sending {} on {}".format(action, process, fqdn))
                    producer.publish(
                        {"action": action},
                        exchange=exchange,
                        routing_key=fqdn,
                        declare=[exchange],
                        retry=True,
                    )
                else:
                    logger.debug("connected to message bus, sending {} to {} on {}".format(action, process, fqdn))
                    producer.publish(
                        {"action": action, "process": process},
                        exchange=exchange,
                        routing_key=fqdn,
                        declare=[exchange],
                        retry=True,
                    )
    except (socket.gaierror, socket.timeout, OSError, TimeoutError, ConnectionError, amqp.exceptions.ConnectionError, amqp.exceptions.ChannelError) as e:
        logger.warning("connection error: {}".format(repr(e)))
        logger.debug(traceback.format_exc())
    except Exception as e:
        logger.error("unexpected error: {}".format(repr(e)))
        logger.error(traceback.format_exc())
