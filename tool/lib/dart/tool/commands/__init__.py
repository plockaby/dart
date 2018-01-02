import logging
import dart.common.database
import dart.common.query


class BaseCommand(object):
    def __init__(self, **kwargs):
        # everything needs a logger!
        self.logger = logging.getLogger(__name__)

        # get configuration from options
        self.verbose = kwargs.get("verbose", False)


class DataCommand(BaseCommand):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ignore cassandra errors only if we aren't explicitly in verbose mode
        if (not self.logger.isEnabledFor(logging.DEBUG)):
            logging.getLogger("cassandra").setLevel(logging.ERROR)

        # we ignore warnings when trying to connect because our user doesn't
        # really care if a node is down. if all nodes are down then we still
        # bomb out. here we are just establishing the initial session.
        self.logger.debug("getting cassandra session")
        self.session = dart.common.database.session()
        if (self.session is None):
            raise RuntimeError("could not get connection to cassandra")

        # now assign the session function to the dart query handler
        dart.common.query.session = self.session

    def __del__(self):
        try:
            self.session.shutdown()
        except Exception as e:
            pass
