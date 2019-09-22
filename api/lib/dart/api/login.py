import logging
from flask_login import UserMixin
from werkzeug.exceptions import Unauthorized
import dart.common.http


# we want to set up a separate logger
logger = logging.getLogger(__name__)


# used by the login manager below
class AuthenticatedLogin(UserMixin):
    def __init__(self):
        self._source = {}

    @property
    def source(self):
        return self._source


def register_login_handler(app):
    # import all of the things that we need from the loader
    from .app import login_manager, settings_manager

    # ensure that we were given either a token or an ssl certificate
    @login_manager.request_loader
    def load_login_from_request(request):
        # who did our login come from
        ip_address = dart.common.http.get_ip_address(request)

        # this is the user information
        login = AuthenticatedLogin()
        login.source["ip"] = ip_address

        # haproxy validates that the certificate was issued by uwca. if we have
        # this header then it means that haproxy was happy with the client's
        # certificate. flask also screws around with the capitalization of
        # headers so that's why that looks weird here.
        cn = request.headers.get("X-Ssl-Client-Cn")
        if (cn is not None and cn.strip() != ""):
            cn = cn.strip()
            logger.info("received connection from {} with certificate '{}'".format(ip_address, cn))

            if (cn in settings_manager.settings.get("authorized", [])):
                logger.info("allowing access via SSL from {}".format(cn))

                # record the cn that got the user in
                login.source["type"] = "cn"
                login.source["id"] = cn
                return login
            else:
                logger.info("denying access from {} using invalid certificate cn {}".format(ip_address, cn))
                raise Unauthorized("The client certificate you have provided is not authorized to access this API.")

        # completely invalid login, no credentials, don't allow in. we could
        # just return None and accomplish the same thing but we want to provide
        # a nice messages when the user is unauthorized.
        logger.info("received connection from {} without any authorization information".format(ip_address))
        raise Unauthorized("You must provide either a valid client certificate to use this API.")
