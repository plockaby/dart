from .app import logger
from flask import request
from flask_login import current_user
from werkzeug.exceptions import BadRequest
import functools
import json


# this will validate that we got valid json data
def validate_json_data(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        # make sure that we were given a request body
        if (not request.data):
            logger.warning("received empty data from {}".format(current_user.source))
            raise BadRequest("The DartAPI received an empty message. You must POST data in the body of the request to use the DartAPI.")

        # make sure that it is valid utf8 data
        try:
            data = request.data.decode("utf8")
        except UnicodeDecodeError:
            logger.warning("received non-UTF-8 data from {}".format(current_user.source))
            raise BadRequest("The DartAPI received non-UTF-8 data that could not be decoded. You must send data only in UTF-8.")

        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("received non-JSON data from {}".format(current_user.source))
            raise BadRequest("The DartAPI received non-JSON data that could not be parsed. You must send only valid JSON data.")

        # make sure we have some data
        if (data is None):
            logger.warning("received no data from {}".format(current_user.source))
            raise BadRequest("The DartAPI received no data. You must send valid JSON data.")

        request.data = data
        return f(*args, **kwargs)

    return wrapped
