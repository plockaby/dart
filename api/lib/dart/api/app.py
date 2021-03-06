import os
import logging
from flask import Flask
from flask_login import LoginManager
from dart.common.settings import SettingsManager
from .database import DatabaseClient
from . import login
from . import errors


# enable a logger
logging.captureWarnings(True)
logger = logging.getLogger(__name__)

# get global settings
settings_manager = SettingsManager(lazy=True)

# need a connection to the database
db_client = DatabaseClient()

# create a login manager
login_manager = LoginManager()


def load():
    app = Flask(__name__, static_folder=None)
    if ("FLASK_CONFIG" in os.environ):
        app.config.from_envvar("FLASK_CONFIG")

    # tell the logs what version we are running
    logger.info("starting in {}".format(app.config.get("ENVIRONMENT", "development")))

    # let the api be accessible from wherever
    @app.after_request
    def add_header(r):
        r.headers["Access-Control-Allow-Origin"] = "*"
        r.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
        r.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return r

    # initialize settings
    settings_manager.init_app(app)

    # initialize global error handlers
    errors.register_error_handler(app)

    # connect to the database
    db_client.init_app(
        app,
        settings_manager.get("api.database.name", "dart"),
        # get all database configuration values and remove the leading parts
        **({k.split(".")[-1]: v for k, v in settings_manager.items() if (k.startswith("api.database") and k != "api.database.name")})
    )

    # initialize the login manager
    login_manager.init_app(app)
    login.register_login_handler(app)

    # routes that the agent will query
    from .blueprints.agent.v1 import v1
    prefix = "{}/agent/v1".format(app.config.get("APPLICATION_ROOT", ""))
    logger.info("using application url prefix {}".format(prefix))
    app.register_blueprint(v1, url_prefix=prefix)

    # routes that the tool/portal will query
    from .blueprints.tool.v1 import v1
    prefix = "{}/tool/v1".format(app.config.get("APPLICATION_ROOT", ""))
    logger.info("using application url prefix {}".format(prefix))
    app.register_blueprint(v1, url_prefix=prefix)

    # routes to coordinate remote systems
    from .blueprints.coordination.v1 import v1
    prefix = "{}/coordination/v1".format(app.config.get("APPLICATION_ROOT", ""))
    logger.info("using application url prefix {}".format(prefix))
    app.register_blueprint(v1, url_prefix=prefix)

    # tell ourselves what we've mapped.
    if (logger.isEnabledFor(logging.DEBUG)):
        for url in app.url_map.iter_rules():
            logger.debug(repr(url))

    return app
