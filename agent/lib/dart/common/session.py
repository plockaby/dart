from flask import request, session
import dart.common.http
import functools


# this should be put around each html call
def require_authentication(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        username = dart.common.http.get_user_name(request)
        if (not username):
            import werkzeug.exceptions
            raise werkzeug.exceptions.Unauthorized("You do not have access to this resource. Please try logging in again.")
        else:
            session["username"] = username

            return f(*args, **kwargs)

    return wrapped


# this should be put around each xhr call
def require_session(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        username = session.get("username")
        if (not username):
            import werkzeug.exceptions
            raise werkzeug.exceptions.Unauthorized("You do not have access to this resource. Please try logging in again.")
        else:
            return f(*args, **kwargs)

    return wrapped
