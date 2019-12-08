import logging
from flask_login import UserMixin
from werkzeug.exceptions import Unauthorized
import dart.common.http


# we want to set up a separate logger
logger = logging.getLogger(__name__)


# used by the login manager below
class AuthenticatedLogin(UserMixin):
    pass


def register_login_handler(app):
    # import all of the things that we need from the loader
    from .app import login_manager

    # ensure that we have a username
    @login_manager.request_loader
    def load_login_from_request(request):
        username = dart.common.http.get_user_name(request)
        if (username is None):
            logger.info("no authorized user found for request to {}".format(request.endpoint))
            raise Unauthorized("You are not authorized to access this resource.")

        # this is the user information
        logger.info("authorized access for {} to {}".format(username, request.endpoint))
        login = AuthenticatedLogin()
        login.username = username
        return login
