import logging
import dart.common.configuration
import dart.common.monkey
import threading
import cassandra
import cassandra.auth
import cassandra.cluster
import cassandra.policies
import cassandra.query
import traceback
import time
import os


# used for logging
logger = logging.getLogger(__name__)

# keep track of all of the database sessions. the key is the combo of process
# and thread id. unlike the flask connector, this does not need a lock on it
# because we aren't sharing connections between threads and access to the dict
# is atomic when checking or inserting something.
sessions = dict()


def session(killer=None):
    # the session id is used to determine if we need a new connection
    session_id = _get_session_id()
    if (session_id not in sessions):
        sessions[session_id] = None

    # try to get it out of our sessions dict and return it if it is there
    session = sessions[session_id]
    if (session is not None):
        logger.debug("reusing cassandra session for {}".format(session_id))
        return session

    # get the session to cassandra up front and let it maintain it. as long as
    # it can get a session at startup then it does a good job maintaining it.
    connected = False
    while (not connected and (killer is None or not killer.killed())):
        logger.debug("attempting to create new cassandra session for {}".format(session_id))
        try:
            configuration = dart.common.configuration.load()
            cluster = cassandra.cluster.Cluster(
                auth_provider=DartAuthProvider(),
                # the driver automatically chooses the "best" host
                contact_points=configuration["cassandra"]["addresses"],
                # want to connect to whatever is available
                load_balancing_policy=cassandra.policies.RoundRobinPolicy(),
                # we never want to stop trying to connect to a host. try to
                # connect once per minute to all hosts in our host list.
                reconnection_policy=cassandra.policies.ConstantReconnectionPolicy(60, max_attempts=None),
                # try to connect to three hosts at the same time
                executor_threads=3,
            )
            session = cluster.connect()

            # want dicts back from our queries
            session.row_factory = cassandra.query.dict_factory

            # we only need to talk to one replica
            session.default_consistency_level = cassandra.ConsistencyLevel.ONE

            # save this session with the connection id
            sessions[session_id] = session

            connected = True
        except (OSError, cassandra.cluster.NoHostAvailable) as e:
            logger.warning("no cassandra hosts available: {}".format(repr(e)))
            logger.debug(traceback.format_exc())
        except Exception as e:
            logger.error("unexpected error: {}".format(repr(e)))
            logger.error(traceback.format_exc())
        finally:
            # we might not be able to check that we were killed in the
            # loop above if we hit an exception while connecting to
            # cassandra so we'll check again here.
            if (not connected and (killer is None or not killer.killed())):
                interval = 10
                logger.warn("sleeping for {} seconds before trying again".format(interval))
                time.sleep(interval)

    # this might be "none" if the client wasn't connected
    return sessions[session_id]


def _get_session_id():
    if (dart.common.monkey.is_patched()):
        return os.getpid()
    else:
        # yes, thread ids "may be recyled when a thread exits and another
        # thread is created" but since this value is never getting communicated
        # to other threads then it is ok to use it here to identify ourselves.
        return "{}-{}".format(os.getpid(), threading.current_thread().ident)


# used by cassandra to look up the password again when necessary
class DartAuthProvider(cassandra.auth.AuthProvider):
    def new_authenticator(self, host):
        return DartAuthenticator()


# used by cassandra to look up the password again when necessary
class DartAuthenticator(cassandra.auth.Authenticator):
    def initial_response(self):
        configuration = dart.common.configuration.load()
        username = configuration["cassandra"]["username"]
        password = configuration["cassandra"]["password"]
        return "\x00%s\x00%s" % (username, password)

    def evaluate_challenge(self, challenge):
        return None
