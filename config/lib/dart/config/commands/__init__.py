import logging
import dart.common.database


class BaseCommand(object):
    def __init__(self, **kwargs):
        # everything needs a logger!
        self.logger = logging.getLogger(__name__)

        # get configuration from options
        self.verbose = kwargs.get("verbose", False)

        # ignore cassandra errors only if we aren't explicitly in verbose mode
        if (not self.logger.isEnabledFor(logging.DEBUG)):
            logging.getLogger("cassandra").setLevel(logging.ERROR)

        # we ignore warnings when trying to connect because our user doesn't
        # really care if a node is down. if all nodes are down then we still
        # bomb out.
        self.logger.debug("getting cassandra session")
        self.session = dart.common.database.session()
        if (self.session is None):
            raise RuntimeError("could not get connection to cassandra")

    def __del__(self):
        try:
            self.session.shutdown()
        except Exception:
            pass
