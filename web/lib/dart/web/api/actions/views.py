from flask import jsonify, request, make_response
from . import api
from ... import logger
import dart.common.remote
import dart.common.query as q
import dart.common.exceptions as exceptions
import traceback


@api.route("/assign")
def assign():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    process = request.args.get("process")
    environment = request.args.get("environment")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)
    if (not environment):
        return make_response(jsonify(dict(error="missing environment")), 400)

    logger.info("assigning {} {} to {}".format(process, environment, fqdn))
    try:
        q.assign(process, environment, fqdn)

        # send a rewrite command to the host to get results faster but we don't
        # care tooooo much if this fails right now
        try:
            dart.common.remote.command(fqdn, "rewrite")
        except Exception as e:
            pass

        return make_response(jsonify(dict()), 200)
    except (exceptions.DartHostDoesNotExistException, exceptions.DartProcessEnvironmentDoesNotExistException) as e:
        return make_response(jsonify(dict(error="could not assign {} {} to {}: {}".format(process, environment, fqdn, e))), 406)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error assigning {} {} to {}: {}".format(process, environment, fqdn, e))), 500)


@api.route("/unassign")
def unassign():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    logger.info("unassigning {} from {}".format(process, fqdn))
    try:
        q.unassign(process, fqdn)

        # send a rewrite command to the host to get results faster but we don't
        # care tooooo much if this fails right now
        try:
            dart.common.remote.command(fqdn, "rewrite")
        except Exception as e:
            pass

        return make_response(jsonify(dict()), 200)
    except (exceptions.DartHostDoesNotExistException, exceptions.DartProcessDoesNotExistException) as e:
        return make_response(jsonify(dict(error="could not unassign {} from {}: {}".format(process, fqdn, e))), 406)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error unassigning {} from {}: {}".format(process, fqdn, e))), 500)


@api.route("/enable")
def enable():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    logger.info("enabling {} on {}".format(process, fqdn))
    try:
        q.enable(process, fqdn)

        # send a rewrite command to the host to get results faster but we don't
        # care tooooo much if this fails right now
        try:
            dart.common.remote.command(fqdn, "rewrite")
        except Exception as e:
            pass

        return make_response(jsonify(dict()), 200)
    except (exceptions.DartHostDoesNotExistException, exceptions.DartProcessDoesNotExistException, exceptions.DartProcessNotAssignedException) as e:
        return make_response(jsonify(dict(error="could not enable {} on {}: {}".format(process, fqdn, e))), 406)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error enabling {} on {}: {}".format(process, fqdn, e))), 500)


@api.route("/disable")
def disable():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    logger.info("disabling {} on {}".format(process, fqdn))
    try:
        q.disable(process, fqdn)

        # send a rewrite command to the host to get results faster but we don't
        # care tooooo much if this fails right now
        try:
            dart.common.remote.command(fqdn, "rewrite")
        except Exception as e:
            pass

        return make_response(jsonify(dict()), 200)
    except (exceptions.DartHostDoesNotExistException, exceptions.DartProcessDoesNotExistException, exceptions.DartProcessNotAssignedException) as e:
        return make_response(jsonify(dict(error="could not disable {} on {}: {}".format(process, fqdn, e))), 406)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error disabling {} on {}: {}".format(process, fqdn, e))), 500)
