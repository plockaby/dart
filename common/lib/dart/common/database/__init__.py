import logging
import psycopg2
from psycopg2.extensions import TRANSACTION_STATUS_UNKNOWN, TRANSACTION_STATUS_IDLE
import threading
import tenacity
import traceback


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
