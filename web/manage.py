#!/usr/bin/env python3

import os
import sys
import click
import logging
from flask.cli import FlaskGroup


# really don't want to write bytecode
sys.dont_write_bytecode = True

# include lib directory in default path
path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, "{}/lib".format(path))

# tell flask where its configuration is
os.environ["FLASK_ENV"] = os.environ.get("FLASK_ENV", "development")
os.environ["FLASK_CONFIG"] = os.environ.get("FLASK_CONFIG", "{}/lib/dart/web/configurations/development.cfg".format(path))

# set up logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_handler = logging.StreamHandler(stream=sys.stdout)
log_handler.setFormatter(logging.Formatter("[%(asctime)s] (%(pathname)s:%(lineno)d) %(levelname)-8s - %(message)s"))
logger.addHandler(log_handler)


def create_app(info):
    import dart.common.monkey
    dart.common.monkey.patch()

    from dart.web import load
    return load()


@click.group(cls=FlaskGroup, create_app=create_app)
def run():
    pass


if __name__ == '__main__':
    run()
