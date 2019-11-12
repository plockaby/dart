import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import TRANSACTION_STATUS_UNKNOWN, TRANSACTION_STATUS_IDLE
from flask import session, g
import threading
import tenacity
import uuid
import traceback
import pwd
import os


# we want to set up a separate logger
logger = logging.getLogger(__name__)


class PoolError(psycopg2.Error):
    pass


class ConnectionPool:
    def __init__(self, minconn, maxconn, *args, **kwargs):
        self.minconn = int(minconn)
        self.maxconn = int(maxconn)

        self._args = args
        self._kwargs = kwargs

        self._pool = []   # connections that are available
        self._used = {}   # connections currently in use

        # control access to the thread pool
        self._lock = threading.RLock()

    def getconn(self, key):
        with self._lock:
            # this key already has a connection so return it
            if (key in self._used):
                return self._used[key]

            # our pool is currently empty
            if (len(self._pool) == 0):
                # we've given out all of the connections that we want to
                if (len(self._used) == self.maxconn):
                    raise PoolError("connection pool exhausted")

                # get a connection but do it with a retry
                conn = self._connect()

                # add to the list of available connections
                self._pool.append(conn)

            # take a connection out of the pool and give it away
            self._used[key] = conn = self._pool.pop()
            return conn

    def putconn(self, key, close=False):
        with self._lock:
            conn = self.getconn(key)
            if (conn is None):
                raise PoolError("no connection with that key")

            if (len(self._pool) < self.minconn and not close):
                # Return the connection into a consistent state before putting
                # it back into the pool
                status = conn.info.transaction_status
                if (status == TRANSACTION_STATUS_UNKNOWN):
                    # server connection lost
                    conn.close()
                elif (status != TRANSACTION_STATUS_IDLE):
                    # connection in error or in transaction
                    conn.rollback()
                    self._pool.append(conn)
                else:
                    # regular idle connection
                    self._pool.append(conn)
            else:
                conn.close()

            # here we check for the presence of key because it can happen that
            # a thread tries to put back a connection after a call to close
            if (key in self._used):
                del self._used[key]

    # retry with a random value between every 0.5 and 1.5 seconds
    @tenacity.retry(wait=tenacity.wait_fixed(0.5) + tenacity.wait_random(0, 1.5), before=tenacity.before_log(logger, logging.DEBUG))
    def _connect(self):
        try:
            # connect to the database with the arguments provided when the pool was
            # initialized. enable autocommit for consistency. this will retry using
            # the "tenacity" library.
            conn = psycopg2.connect(*self._args, **self._kwargs)
            conn.autocommit = True
            return conn
        except Exception as e:
            logger.warning("could not connect to the database: {}".format(e))
            logger.debug(traceback.format_exc())
            raise


class DatabaseClient:
    def __init__(self, app=None, **kwargs):
        if (app is not None):
            self.init_app(app, **kwargs)
        else:
            self.app = None

    def init_app(self, app, key, minconn=2, maxconn=16, **kwargs):
        self.app = app

        # this is how we will find the database connection client identifier
        # for this request. this lets the library ensure that it is handing out
        # the same connection for the duration of the request.
        self.key = "db_client_key[{}]".format(key)

        # initialize the connection pool
        self.pool = ConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            cursor_factory=RealDictCursor,
            **kwargs,
        )

        # this will clean up the connection when it is done
        self.app.teardown_request(self.close)

    def conn(self):
        # loop until we have a database connection
        db_client = None
        while (db_client is None):
            # see if we have a database client identifier for this request
            # already. if we have a client identifier then get the connection
            # associated with that identifier and test if it is still alive. if
            # it is alive then return it. if it is not alive then raise an
            # exception because we want to return the same connection through
            # an entire request. if we do NOT have a client identifier then
            # get a connection and test it until we get a connection that is
            # alive.
            db_client_id = None
            if (hasattr(g, self.key)):
                # try to get a connection with this client id
                db_client_id = str(getattr(g, self.key))
                db_client = self._get_connection(db_client_id)

                # no connection returned for the request's client identifier so
                # the connection is dead and we can't do anything.
                if (db_client is None):
                    delattr(g, self.key)  # remove client identifier
                    raise PoolError("request connection lost")

                # actually the client identifier returned a valid connection
                return db_client

            # try to get a connection with a new identifier
            db_client_id = str(uuid.uuid4())
            db_client = self._get_connection(db_client_id)

            # the connection that we got was valid so let's save the identifier
            # and return the connection. (if it wasn't valid then we'll just
            # repeate the loop which is a-ok.)
            if (db_client is not None):
                # do anything with a new connection here. for example, maybe
                # you want to set a configuration value that use the person's
                # username in it. i don't know. TODO

                # set a username if we know it as this lets modified_by columns
                # work. we absolutely want to reset the username each time we
                # hand a connection back, even if we can't find a username. if
                # we don't then it's possible that we could inadvertently reuse
                # username from a previous request which would be incorrect.
                username = session.get("username", pwd.getpwuid(os.getuid())[0]) or "dart"
                cur = db_client.cursor()
                cur.execute("SELECT set_config('local.userid', %s, FALSE)", [username])
                cur.close()

                # then attach the connection to the request global
                setattr(g, self.key, db_client_id)
                return db_client

    def close(self, exception):
        # this gets called when a request is finished, regardless of the state
        # of the request (e.g. success [2xx] or failure [4xx, 5xx])
        if (hasattr(g, self.key)):
            try:
                db_client_id = getattr(g, self.key)
                self.pool.putconn(db_client_id)
                logger.debug("returned connection {} to pool named {}".format(db_client_id, self.key))
            except (PoolError, KeyError) as e:
                logger.error("could not return connection to pool: {}".format(repr(e)))

    def _get_connection(self, db_client_id):
        db_client = self.pool.getconn(db_client_id)

        try:
            logger.debug("testing connection {} from pool named {}".format(db_client_id, self.key))

            # test the connection before giving it back to ensure it works.
            # if it doesn't work then we're going to close it and try to
            # get a different connection until we find one that works.
            cur = db_client.cursor()
            cur.execute("SELECT pg_backend_pid()")
            cur.close()
        except Exception as e:
            logger.warning("connection {} from pool named {} failed: {}".format(db_client_id, self.key, e))

            # we do not have a valid connection so put it back and close it
            # and set our current db_client to None so that our next time
            # around the loop will attempt to get a new connection.
            self.pool.putconn(db_client_id, close=True)

            # the connection was bad
            return
        else:
            logger.debug("using connection {} from pool named {}".format(db_client_id, self.key))

            # the connection was good
            return db_client
