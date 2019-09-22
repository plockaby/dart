import logging
import traceback
import werkzeug.exceptions
from flask import make_response, jsonify


# we want to set up a separate logger
logger = logging.getLogger(__name__)


# errors MUST be registered here and NOT in the blueprints. blueprints cannot
# handle most of the error types because the errors get intercepted before they
# get routed to a blueprint. so we put them all here.
def register_error_handler(app):
    def error_handler(e):
        return make_response(jsonify({
            "code": e.code,
            "message": e.description,
        }), e.code)

    # now just register every possible exception
    for exception in werkzeug.exceptions.default_exceptions:
        app.register_error_handler(exception, error_handler)

    # a special case to catch internal errors. the code above does not catch
    # generic exceptions thrown from our program. this does plus it does some
    # extra logging to help detect and debug these.
    @app.errorhandler(Exception)
    def server_error(e):
        # we're going to crib off of the default exceptions
        exception = werkzeug.exceptions.InternalServerError

        # for these we would like a stack trace
        logger.error("internal server error: {}".format(e))
        logger.error(traceback.format_exc())

        # then it's just a normal json exception
        return error_handler(exception)
