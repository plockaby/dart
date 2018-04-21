import os
import logging
from flask import Flask
from flask_moment import Moment
import dart.common.configuration
from dart.web.database import CassandraClient
from datetime import datetime


# enable a logger
logging.captureWarnings(True)
logger = logging.getLogger(__name__)

# these things defined here get used by views, forms, and errors
db_client = CassandraClient()

# used to format dates all pretty
moment = Moment()


def load():
    app = Flask(__name__, static_folder=None)
    if ("FLASK_CONFIG" in os.environ):
        app.config.from_envvar("FLASK_CONFIG")

    # disable debug logging for kombu and cassandra
    logging.getLogger("kombu").setLevel(logging.INFO)
    logging.getLogger("cassandra").setLevel(logging.INFO)

    # initialize the cassandra thingy
    configuration = dart.common.configuration.load()
    db_client.init_app(app, configuration["cassandra"]["addresses"])

    # initialize the date formatter
    moment.init_app(app)

    # we want our templates to always know the current time
    @app.context_processor
    def inject_now():
        return {"now": datetime.utcnow()}

    # register the blueprint using the prefix defined in the configuration as
    # the application root. if APPLICATION_ROOT is defined incorrectly then
    # this whole thing will break. multiple blueprints may be defined with a
    # different value for "url_prefix" but all blueprints SHOULD begin with the
    # same prefix defined in APPLICATION_ROOT.
    from .main import main
    prefix = app.config.get("APPLICATION_ROOT", "")
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

    # tell ourselves what we've mapped.
    if (logger.isEnabledFor(logging.DEBUG)):
        for url in app.url_map.iter_rules():
            logger.debug(repr(url))

    return app
