from flask import jsonify, request, make_response
from . import api
from ... import logger
import dart.common.query as q
import traceback


@api.route("/")
def processes():
    try:
        processes = q.processes()

        # convert the sets to lists so that we can serialize this with json
        for process in processes:
            processes[process]["active_hosts"] = list(processes[process]["active_hosts"])
            processes[process]["pending_hosts"] = list(processes[process]["pending_hosts"])
            processes[process]["assigned_hosts"] = list(processes[process]["assigned_hosts"])
            processes[process]["disabled_hosts"] = list(processes[process]["disabled_hosts"])

        return make_response(jsonify(list(processes.values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting processes: {}".format(e))), 500)


@api.route("/process")
def process():
    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    try:
        # now get some generic information
        configurations = q.process(process)

        # get monitoring information from cassandra
        daemon_monitoring = q.process_daemon_monitoring_configuration(process)
        state_monitoring = q.process_state_monitoring_configuration(process)
        log_monitoring = q.process_log_monitoring_configurations(process)

        return make_response(jsonify(
            configurations=configurations,
            monitoring=dict(
                daemon=daemon_monitoring,
                state=state_monitoring,
                log=log_monitoring,
            )
        ), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting details for process named {}: {}".format(process, e))), 500)


@api.route("/process/active")
def active():
    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    try:
        hosts = q.process_active(process)
        assigned = q.process_assigned(process)
        for fqdn in hosts:
            if (fqdn in assigned):
                if (assigned[fqdn]["schedule"]):
                    hosts[fqdn]["schedule"] = assigned[fqdn]["schedule"]
                    hosts[fqdn]["starts"] = assigned[fqdn]["starts"]
                if (assigned[fqdn]["daemon"]):
                    hosts[fqdn]["daemon"] = assigned[fqdn]["daemon"]

        return make_response(jsonify(list(hosts.values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting active hosts for process named {}: {}".format(process, e))), 500)


@api.route("/process/pending")
def pending():
    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    try:
        return make_response(jsonify(list(q.process_pending(process).values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting pending hosts for process named {}: {}".format(process, e))), 500)


@api.route("/process/assigned")
def assigned():
    process = request.args.get("process")
    if (not process):
        return make_response(jsonify(dict(error="missing process name")), 400)

    try:
        return make_response(jsonify(list(q.process_assigned(process).values())), 200)
    except Exception as e:
        logger.error(traceback.format_exc())
        return make_response(jsonify(dict(error="error getting assigned hosts for process named {}: {}".format(process, e))), 500)
