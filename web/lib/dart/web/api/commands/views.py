from flask import jsonify, request, make_response
from . import api
from ... import logger
import dart.common.remote
import dart.common.query as q
import traceback


@api.route("/start")
def start():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    if (process == "dart-agent"):
        return make_response(jsonify(dict(error="no changes allowed to dart-agent")), 400)

    logger.info("starting {} on {}".format(process, fqdn))
    try:
        dart.common.remote.command(fqdn, "start", process)
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/stop")
def stop():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    if (process == "dart-agent"):
        return make_response(jsonify(dict(error="no changes allowed to dart-agent")), 400)

    logger.info("stopping {} on {}".format(process, fqdn))
    try:
        dart.common.remote.command(fqdn, "stop", process)
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/restart")
def restart():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    if (process == "dart-agent"):
        return make_response(jsonify(dict(error="no changes allowed to dart-agent")), 400)

    logger.info("restarting {} on {}".format(process, fqdn))
    try:
        dart.common.remote.command(fqdn, "restart", process)
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/add")
def add():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    if (process == "dart-agent"):
        return make_response(jsonify(dict(error="no changes allowed to dart-agent")), 400)

    logger.info("adding {} on {}".format(process, fqdn))
    try:
        dart.common.remote.command(fqdn, "add", process)
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/remove")
def remove():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    if (process == "dart-agent"):
        return make_response(jsonify(dict(error="no changes allowed to dart-agent")), 400)

    logger.info("removing {} on {}".format(process, fqdn))
    try:
        dart.common.remote.command(fqdn, "remove", process)
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/update")
def update():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    if (process == "dart-agent"):
        return make_response(jsonify(dict(error="no changes allowed to dart-agent")), 400)

    logger.info("updating {} on {}".format(process, fqdn))
    try:
        dart.common.remote.command(fqdn, "update", process)
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/reread")
def reread():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    logger.info("rereading {}".format(fqdn))
    try:
        dart.common.remote.command(fqdn, "reread")
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)


@api.route("/rewrite")
def rewrite():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)
    if (not q.is_valid_host(fqdn)):
        return make_response(jsonify(dict(error="{} is not the name of a valid host".format(fqdn))), 400)

    logger.info("rewriting {}".format(fqdn))
    try:
        dart.common.remote.command(fqdn, "rewrite")
        return make_response(jsonify(dict()), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error sending command: {}".format(e))), 500)
