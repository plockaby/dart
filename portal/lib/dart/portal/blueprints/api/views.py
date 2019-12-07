from ...app import logger
from ...app import cache
from ... import requests as r
from . import api
from flask import make_response, jsonify, request
from dart.common.html import sanitize
from dart.common import PROCESSES_TO_IGNORE
import requests
import traceback
import yaml


@api.route("/hosts", methods=["GET"])
def hosts():
    try:
        @cache.cached(timeout=10, key_prefix="api/select/hosts")
        def select():
            return r.select_hosts()

        results = list(filter(lambda x: x["polled"] is not None, select()))
        return make_response(jsonify(results), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/hosts/autocomplete", methods=["GET"])
def autocomplete_host():
    try:
        search = request.args.get("q")
        results = []

        @cache.cached(timeout=60, key_prefix="api/hosts/autocomplete")
        def get_results():
            return r.select_hosts()

        if (search):
            search = search.lower()
            results = filter(lambda x: x.startswith(search), map(lambda x: x["fqdn"], get_results()))

        return make_response(jsonify({"results": sorted(results)}), 200)
    except Exception:
        logger.debug(traceback.format_exc())
        return make_response(jsonify([]), 200)


@api.route("/host/<string:fqdn>/active", methods=["GET"])
def host_active(fqdn):
    try:
        @cache.cached(timeout=1, key_prefix="api/host/{}".format(fqdn))
        def select():
            return r.select_host(fqdn)

        result = select()
        if (result is None):
            return make_response(jsonify([]), 404)
        else:
            return make_response(jsonify(result["active"]), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/host/<string:fqdn>/pending", methods=["GET"])
def host_pending(fqdn):
    try:
        @cache.cached(timeout=1, key_prefix="api/host/{}".format(fqdn))
        def select():
            return r.select_host(fqdn)

        result = select()
        if (result is None):
            return make_response(jsonify([]), 404)
        else:
            return make_response(jsonify(result["pending"]), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/host/<string:fqdn>/assigned", methods=["GET"])
def host_assigned(fqdn):
    try:
        @cache.cached(timeout=1, key_prefix="api/host/{}".format(fqdn))
        def select():
            return r.select_host(fqdn)

        result = select()
        if (result is None):
            return make_response(jsonify([]), 404)
        else:
            return make_response(jsonify(result["assignments"]), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/host/<string:fqdn>", methods=["DELETE"])
def delete_host(fqdn):
    try:
        try:
            r.delete_host(fqdn)
            cache.clear()
            return make_response(jsonify({}), 200)
        except requests.RequestException as e:
            response = e.response.json()
            return make_response(jsonify({"code": response["code"], "message": sanitize(response["message"])}), response["code"])
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/processes", methods=["GET"])
def processes():
    try:
        @cache.cached(timeout=10, key_prefix="api/select/processes")
        def select():
            return r.select_processes()

        results = select()
        return make_response(jsonify(results), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/processes/autocomplete", methods=["GET"])
def autocomplete_process():
    try:
        search = request.args.get("q")
        results = []

        @cache.cached(timeout=60, key_prefix="api/autocomplete/process")
        def get_results():
            return r.select_processes()

        if (search):
            search = search.lower()
            results = filter(lambda x: x.startswith(search), map(lambda x: x["name"], get_results()))

        return make_response(jsonify({"results": sorted(results)}), 200)
    except Exception:
        logger.debug(traceback.format_exc())
        return make_response(jsonify([]), 200)


@api.route("/processes/autocomplete/environment/<string:process_name>", methods=["GET"])
def autocomplete_process_environment(process_name):
    try:
        search = request.args.get("q")
        results = []

        @cache.cached(timeout=60, key_prefix="api/autocomplete/process/{}/environment".format(process_name))
        def get_results():
            return r.select_process(process_name)

        if (search):
            search = search.lower()
            results = filter(lambda x: x.startswith(search), map(lambda x: x["name"], get_results()["environments"]))

        return make_response(jsonify({"results": sorted(results)}), 200)
    except Exception:
        logger.debug(traceback.format_exc())
        return make_response(jsonify([]), 200)


@api.route("/process/<string:name>/active", methods=["GET"])
def process_active(name):
    try:
        @cache.cached(timeout=1, key_prefix="api/process/{}".format(name))
        def select():
            return r.select_process(name)

        result = select()
        if (result is None):
            return make_response(jsonify([]), 404)
        else:
            return make_response(jsonify(result["active"]), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/process/<string:name>/pending", methods=["GET"])
def process_pending(name):
    try:
        @cache.cached(timeout=1, key_prefix="api/process/{}".format(name))
        def select():
            return r.select_process(name)

        result = select()
        if (result is None):
            return make_response(jsonify([]), 404)
        else:
            return make_response(jsonify(result["pending"]), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/process/<string:name>/assigned", methods=["GET"])
def process_assigned(name):
    try:
        @cache.cached(timeout=1, key_prefix="api/process/{}".format(name))
        def select():
            return r.select_process(name)

        result = select()
        if (result is None):
            return make_response(jsonify([]), 404)
        else:
            return make_response(jsonify(result["assignments"]), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/process/<string:name>", methods=["DELETE"])
def delete_process(name):
    try:
        if (name in PROCESSES_TO_IGNORE):
            return make_response(jsonify({"code": 400, "message": "No changes are allowed to the {} process.".format(sanitize(name))}), 400)

        try:
            r.delete_process(name)
            cache.clear()
            return make_response(jsonify({}), 200)
        except requests.RequestException as e:
            response = e.response.json()
            return make_response(jsonify({"code": response["code"], "message": sanitize(response["message"])}), response["code"])
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/action", methods=["POST"])
def action():
    # this will read a POST message to choose:
    # 1. reread/rewrite a host
    # 2. start/stop/restart/update a process
    # 3. enable/disable a process
    # 4. unassign a process
    # 5. assign a process (only task that needs an environment)

    try:
        action = request.form.get("action")
        if (action is None):
            return make_response(jsonify({"code": 400, "message": "No action defined."}), 400)

        # standardize the action
        action = str(action).lower()

        # all of the things that we could possibly need
        fqdn = request.form.get("fqdn")
        process_name = request.form.get("process_name")
        process_environment = request.form.get("process_environment")

        # everything needs an fqdn
        if (not fqdn):
            return make_response(jsonify({"code": 400, "message": "Missing fully qualified domain name."}), 400)

        # actions that need only an fqdn
        if (action == "reread"):
            r.send_host_command(fqdn, "reread")
            return make_response(jsonify({}), 200)
        if (action == "rewrite"):
            r.send_host_command(fqdn, "rewrite")
            return make_response(jsonify({}), 200)

        # actions that need a process
        if (not process_name):
            return make_response(jsonify({"code": 400, "message": "Missing process name."}), 400)

        # make sure the action isn't against an invalid process
        if (process_name in PROCESSES_TO_IGNORE):
            return make_response(jsonify({"code": 400, "message": "No changes are allowed to the {} process.".format(sanitize(process_name))}), 400)

        if (action == "start"):
            r.send_process_command(fqdn, process_name, "start")
            return make_response(jsonify({}), 200)
        if (action == "stop"):
            r.send_process_command(fqdn, process_name, "stop")
            return make_response(jsonify({}), 200)
        if (action == "restart"):
            r.send_process_command(fqdn, process_name, "restart")
            return make_response(jsonify({}), 200)
        if (action == "update"):
            r.send_process_command(fqdn, process_name, "update")
            return make_response(jsonify({}), 200)
        if (action == "enable"):
            r.enable_process(fqdn, process_name)
            return make_response(jsonify({}), 200)
        if (action == "disable"):
            r.disable_process(fqdn, process_name)
            return make_response(jsonify({}), 200)
        if (action == "unassign"):
            r.unassign_process(fqdn, process_name)
            return make_response(jsonify({}), 200)

        # actions that need an environment
        if (not process_environment):
            return make_response(jsonify({"code": 400, "message": "Missing process environment."}), 400)

        if (action == "assign"):
            r.assign_process(fqdn, process_name, process_environment)
            return make_response(jsonify({}), 200)

        logger.warning("received invalid action: {}".format(action))
        return make_response(jsonify({"code": 400, "message": "Invalid action."}), 400)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)


@api.route("/register", methods=["PUT"])
def register():
    try:
        # make sure that we were given a request body
        if (not request.data):
            return make_response(jsonify({"code": 400, "message": "No registration data provided."}), 400)

        # make sure that it is valid utf8 data
        try:
            data = request.data.decode("utf8")
        except UnicodeDecodeError:
            return make_response(jsonify({"code": 400, "message": "Could not process registration data. The provided data must be UTF-8 encoded."}), 400)

        try:
            data = yaml.load(data, Loader=yaml.SafeLoader)
        except yaml.YAMLError:
            return make_response(jsonify({"code": 400, "message": "Could not process registration data. You have not provided valid YAML data."}), 400)

        # make sure we have some data
        if (data is None):
            return make_response(jsonify({"code": 400, "message": "Could not process registration data. You have not provided valid YAML data."}), 400)

        return make_response(jsonify(r.register(data)), 200)
    except Exception as e:
        logger.error("internal server error: {}".format(str(e)))
        logger.error(traceback.format_exc())
        return make_response(jsonify({"code": 500, "message": sanitize(str(e))}), 500)
