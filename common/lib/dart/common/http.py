import logging


# create a logger for our libraries to use
logger = logging.getLogger(__name__)


def get_ip_address(request):
    ip_addresses = request.headers.get("X-Forwarded-For")
    if (not ip_addresses):
        import werkzeug.exceptions
        raise werkzeug.exceptions.InternalServerError("Missing X-Forwarded-For header.")

    # ip addresses could come in a comma separated list
    import re
    p = re.compile(r"\s*,\s*")
    ip_address_list = re.split(p, ip_addresses)
    if (len(ip_address_list) == 0):
        return request.remote_addr

    if (len(ip_address_list) == 1):
        # if there is only one address then that is the address of the client.
        ip_address = ip_address_list[0]
    else:
        # the X-Forwarded-For field gets populated by proxies. the last proxy
        # in the line before us is haproxy. so we want the second to last
        # because that will be the actual source of our client.
        ip_address = ip_address_list[-2].strip()

    # make sure that we even got an address
    if (not ip_address):
        return request.remote_addr

    return ip_address


# this depends on apache config sticking the identity in somewhere
def get_user_name(request):
    # try the authorization header
    authorization = request.headers.get("Authorization")
    if (authorization):
        import base64
        authorization = authorization.replace("Basic", "", 1).strip()
        try:
            return base64.b64decode(authorization).decode("utf-8").split(":", 1)[0]
        except (TypeError, UnicodeError):
            pass

    # then try the X-Forwarded-User header
    user_name = request.headers.get("X-Forwarded-User")
    if (user_name):
        return user_name

    logger.warning("no username found in headers")
    return
