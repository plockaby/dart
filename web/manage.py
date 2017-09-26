#!/usr/bin/env python3

import os
import sys
import click
from flask.cli import FlaskGroup


# really don't want to write bytecode
sys.dont_write_bytecode = True

# include lib directory in default path
path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, "{}/lib".format(path))

# tell flask where its configuration is
os.environ["FLASK_CONFIG"] = os.environ.get("FLASK_CONFIG", "{}/lib/dart/web/configurations/dev.cfg".format(path))


def create_app(info):
    from dart.web import app
    return app


@click.group(cls=FlaskGroup, create_app=create_app)
def run():
    pass


if __name__ == '__main__':
    run()
