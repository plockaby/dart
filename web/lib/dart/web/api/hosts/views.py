from ... import logger
from . import api
from flask import jsonify, request, make_response
from dart.common.bleach import sanitize
import dart.common.query as q
import traceback


@api.route("/")
def hosts():
    try:
        hosts = q.hosts()

        # remove hosts that are not managed by dart
        hosts = {key: value for key, value in hosts.items() if value["checked"] is not None and value["total"] > 0}

        return make_response(jsonify(list(hosts.values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting hosts: {}".format(sanitize(e)))), 500)


@api.route("/advanced")
def advanced():
    try:
        hosts = q.hosts()

        # get advanced details about each host
        for fqdn in hosts:
            details = q.host(fqdn)
            hosts[fqdn] = {
                **hosts[fqdn],
                **details.get("configuration", dict()),
                **details.get("management", dict()),
                "targets": sorted(q.host_targets(fqdn)),
            }

        return make_response(jsonify(list(hosts.values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting hosts: {}".format(sanitize(e)))), 500)


@api.route("/host")
def host():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    try:
        # now get some generic information
        host = q.host(fqdn)
        tags = q.host_tags(fqdn)

        return make_response(jsonify(
            **host,
            tags=tags,
        ), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting details for host {}: {}".format(sanitize(fqdn), sanitize(e)))), 500)


@api.route("/host/active")
def active():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    try:
        processes = q.host_active(fqdn)
        assigned = q.host_assigned(fqdn)
        for process in processes:
            if (process in assigned):
                if (assigned[process]["schedule"]):
                    processes[process]["schedule"] = assigned[process]["schedule"]
                    processes[process]["starts"] = assigned[process]["starts"]
                if (assigned[process]["daemon"]):
                    processes[process]["daemon"] = assigned[process]["daemon"]

        return make_response(jsonify(list(processes.values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting active processes for host {}: {}".format(sanitize(fqdn), sanitize(e)))), 500)


@api.route("/host/pending")
def pending():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    try:
        return make_response(jsonify(list(q.host_pending(fqdn).values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting pending processes for host {}: {}".format(sanitize(fqdn), sanitize(e)))), 500)


@api.route("/host/assigned")
def assigned():
    fqdn = request.args.get("fqdn")
    if (not fqdn):
        return make_response(jsonify(dict(error="missing fqdn")), 400)

    try:
        return make_response(jsonify(list(q.host_assigned(fqdn).values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting assigned processes for host {}: {}".format(sanitize(fqdn), sanitize(e)))), 500)
