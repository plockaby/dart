from dart.common.database import DartAuthProvider
import dart.common.configuration
import dart.common.query
import dart.common.monkey
import logging
import cassandra
import cassandra.cluster
import cassandra.policies
import cassandra.query
import threading
import os


# we need a logger
logger = logging.getLogger(__name__)

# this keeps track of all of the sessions
sessions = dict()

# the sessions dict needs to be locked before use because we are sharing
# sessions between threads and multiple threads may try to modify the dict
# simultaneously.
sessions_lock = threading.RLock()


class CassandraClient(object):
    def __init__(self, app=None, **kwargs):
        if app is not None:
            self.init_app(app, **kwargs)
        else:
            self._app = None

    def __del__(self):
        try:
            with sessions_lock:
                for session in sessions.values():
                    session.shutdown()
        except Exception as e:
            pass

    def init_app(self, app, servers, client_id="default"):
        self._app = app

        # these things set up config options for the database
        self._servers = servers
        self._client_id = client_id

        # this is used to allow us to connect to multiple databases
        self._dsn_id = self._serialize_dsn(servers, client_id)

        # this means that our global library can use us to get to the database
        dart.common.query.session = self.session

    def _serialize_dsn(self, servers, client_id):
        if (dart.common.monkey.is_patched()):
            logger.info("using a monkey patched cassandra connection")
            return "cassandra_db_{}-{}-{}".format(os.getpid(), ",".join(servers), client_id)
        else:
            return "cassandra_db_{}-{}-{}-{}".format(os.getpid(), threading.current_thread().ident, ",".join(servers), client_id)

    def session(self):
        with sessions_lock:
            if (self._dsn_id not in sessions):
                cluster = cassandra.cluster.Cluster(
                    auth_provider=DartAuthProvider(),
                    # the driver automatically chooses the "best" host
                    contact_points=self._servers,
                    # want to connect to whatever is available
                    load_balancing_policy=cassandra.policies.RoundRobinPolicy(),
                    # we never want to stop trying to connect to a host. try to
                    # connect every ten seconds to all hosts in our host list.
                    reconnection_policy=cassandra.policies.ConstantReconnectionPolicy(10, max_attempts=None),
                    # try to connect to three hosts at the same time
                    executor_threads=3,
                )
                session = cluster.connect()

                # want dicts back from cassandra
                session.row_factory = cassandra.query.dict_factory

                # we only need to talk to one replica
                session.default_consistency_level = cassandra.ConsistencyLevel.ONE

                sessions[self._dsn_id] = session

            return sessions.get(self._dsn_id)
