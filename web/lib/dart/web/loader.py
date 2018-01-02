import os
import sys
import logging
import logging.handlers
from flask import Flask
from flask_moment import Moment
import dart.common.configuration
from dart.web.database import CassandraClient
from datetime import datetime


# enable a logger
logging.captureWarnings(True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# these things defined here get used by views, forms, and errors
db_client = CassandraClient()

# used to format dates all pretty
moment = Moment()


def load():
    app = Flask(__name__, static_folder=None)
    if ("FLASK_CONFIG" in os.environ):
        app.config.from_envvar("FLASK_CONFIG")

    # send logs to stdout
    log_handler = logging.StreamHandler(stream=sys.stdout)

    # enable debug logging if in debug mode
    if app.config.get("DEBUG", False):
        log_handler.setFormatter(logging.Formatter("[%(asctime)s] (%(pathname)s:%(lineno)d) %(levelname)-8s - %(message)s"))
        logger.setLevel(logging.DEBUG)
    else:
        log_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-8s - %(message)s"))

    # our log handler has the log format in it as well as the log destination
    logger.addHandler(log_handler)

    # initialize the cassandra thingy
    configuration = dart.common.configuration.load()
    db_client.init_app(app, configuration["cassandra"]["addresses"])

    # initialize the date formatter
    moment.init_app(app)

    # we want our templates to always know the current time
    @app.context_processor
    def inject_now():
        return {"now": datetime.utcnow()}

    # register our one and only blueprint using the prefix defined in the
    # configuration as the application root.
    from .main import main
    prefix = app.config.get("APPLICATION_ROOT") or "/"
    logger.info("using application url prefix {}".format(prefix))
    app.register_blueprint(main, url_prefix=prefix)

    from .api.commands import api
    api_prefix = "{}/api/command".format(prefix)
    logger.info("using api url prefix {}".format(api_prefix))
    app.register_blueprint(api, url_prefix=api_prefix)

    from .api.actions import api
    api_prefix = "{}/api/action".format(prefix)
    logger.info("using api url prefix {}".format(api_prefix))
    app.register_blueprint(api, url_prefix=api_prefix)

    from .api.hosts import api
    api_prefix = "{}/api/hosts".format(prefix)
    logger.info("using api url prefix {}".format(api_prefix))
    app.register_blueprint(api, url_prefix=api_prefix)

    from .api.processes import api
    api_prefix = "{}/api/processes".format(prefix)
    logger.info("using api url prefix {}".format(api_prefix))
    app.register_blueprint(api, url_prefix=api_prefix)

    return app
