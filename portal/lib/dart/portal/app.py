import os
import logging
from flask import Flask
from flask_moment import Moment
from flask_caching import Cache
from dart.common.settings import SettingsManager
from .api import APIManager
from . import cache_buster


# enable a logger
logging.captureWarnings(True)
logger = logging.getLogger(__name__)

# get global settings
settings_manager = SettingsManager(lazy=True)

# configure access to the api with retries and whatnot
api_manager = APIManager()

# used to format dates all pretty
moment = Moment()

# a basic cache
cache = Cache()


def load():
    app = Flask(__name__, static_folder=None)
    if ("FLASK_CONFIG" in os.environ):
        app.config.from_envvar("FLASK_CONFIG")

    # tell the logs what version we are running
    logger.info("starting in {}".format(app.config.get("ENVIRONMENT", "development")))

    # initialize settings
    settings_manager.init_app(app)

    # initialize the cache busting
    cache_buster.init_app(app)

    # initialize the api manager
    api_manager.init_app(app)

    # initialize the date formatter
    moment.init_app(app)

    # initialize the cache
    cache.init_app(app)

    # register the blueprint using the prefix defined in the configuration as
    # the application root. if APPLICATION_ROOT is defined incorrectly then
    # this whole thing will break. multiple blueprints may be defined with a
    # different value for "url_prefix" but all blueprints SHOULD begin with the
    # same prefix defined in APPLICATION_ROOT.
    from .blueprints.main import main
    prefix = app.config.get("APPLICATION_ROOT", "")
    logger.info("using application url prefix {}".format(prefix))
    app.register_blueprint(main, url_prefix=prefix)

    from .blueprints.api import api
    api_prefix = "{}/api".format(prefix)
    logger.info("using api url prefix {}".format(api_prefix))
    app.register_blueprint(api, url_prefix=api_prefix)

    # tell ourselves what we've mapped.
    if (logger.isEnabledFor(logging.DEBUG)):
        for url in app.url_map.iter_rules():
            logger.debug(repr(url))

    return app
