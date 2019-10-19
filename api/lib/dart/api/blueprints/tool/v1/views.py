from ....app import logger
from ....app import db_client
from ....validators import validate_json_data
from . import v1
from . import queries as q
from flask import jsonify, make_response, request
from flask_login import login_required, current_user
from werkzeug.exceptions import BadRequest, NotFound
from crontab import CronTab
import re


@v1.route("/hosts", methods=["GET"])
@login_required
def hosts():
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False
        hosts = list(q.select_hosts())
        conn.commit()

        return make_response(jsonify(hosts), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


@v1.route("/hosts/<fqdn>", methods=["GET"])
@login_required
def host(fqdn):
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        host = q.select_host(fqdn)
        if (host is None):
            logger.warning("could not get host {} because it was not found".format(fqdn))
            raise NotFound("No host found with the fully qualified domain name {}.".format(fqdn))

        conn.commit()

        return make_response(jsonify(host), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


@v1.route("/hosts/<fqdn>", methods=["DELETE"])
@login_required
def delete_host(fqdn):
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # make sure the host exists
        host = q.select_host(fqdn)
        if (host is None):
            logger.warning("could not delete host {} because it was not found".format(fqdn))
            raise NotFound("No host found with the fully qualified domain name {}.".format(fqdn))

        # make sure the host has nothing assigned to it before deleting
        if (len(host.get("assignments", []))):
            logger.warning("could not delete host {} because it has processes assigned to it".format(fqdn))
            raise BadRequest("Cannot delete host because it has processes assigned to it.")

        q.delete_host(fqdn)
        conn.commit()

        return make_response(jsonify({}), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


@v1.route("/processes", methods=["GET"])
@login_required
def processes():
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False
        processes = list(q.select_processes())
        conn.commit()

        return make_response(jsonify(processes), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


@v1.route("/processes/<name>", methods=["GET"])
@login_required
def process(name):
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        process = q.select_process(name)
        if (process is None):
            logger.warning("could not get process {} because it was not found".format(name))
            raise NotFound("No process found with the name {}.".format(name))

        conn.commit()

        return make_response(jsonify(process), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


@v1.route("/processes/<name>", methods=["DELETE"])
@v1.route("/processes/<name>/<environment>", methods=["DELETE"])
@login_required
def delete_process(name, environment=None):
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # make sure the process is valid
        process = q.select_process(name)
        if (process is None):
            logger.warning("could not delete process {} because it was not found".format(name))
            raise NotFound("No process found with the name {}.".format(name))

        # if we're deleting only one environment then make sure it exists
        if (environment is not None):
            process_environment_found = False
            for x in process["environments"]:
                if (x["name"] == environment):
                    process_environment_found = True
                    break

            if (not process_environment_found):
                logger.warning("could not delete process {} environment {} because it was not found".format(name, environment))
                raise NotFound("No environment found named {} on the process named {}.".format(environment, name))

        # make sure the process isn't assigned to anything
        if (len(process["assignments"]) > 0):
            logger.warning("could not delete process {} because it is assigned to hosts".format(name))
            raise BadRequest("Cannot delete process because it is assigned to hosts.")

        q.delete_process(name, environment)
        conn.commit()

        return make_response(jsonify({}), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


# assign or unassign a process from a host
@v1.route("/hosts/<fqdn>", methods=["PATCH"])
@login_required
@validate_json_data
def change_host(fqdn):
    # make a copy of the request data. this should be a valid python object
    # since our "validate_json_data" call cleaned it up.
    data = request.data

    # to help with debugging
    logger.debug("received host change request from {}: {}".format(current_user.source, data))

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # make sure the host is valid
        if (not q.is_valid_host(fqdn)):
            logger.warning("could not change host {} because it was not found".format(fqdn))
            raise NotFound("No host found with the fully qualified domain name {}.".format(fqdn))

        # we need all of these fields
        if ("op" not in data or "path" not in data or "value" not in data):
            logger.warning("could not change host {} because the patch data was missing fields".format(fqdn))
            raise BadRequest("Invalid PATCH data. Must include fields 'op', 'patch', and 'value'.")

        # make sure the fields look good
        if (data["op"] is None or not isinstance(data["op"], str) or not data["op"].strip() or data["op"] not in ["add", "remove", "replace"]):
            logger.warning("could not change host {} because the operation value was invalid: {}".format(fqdn, data["op"]))
            raise BadRequest("Invalid PATCH data. The 'op' field must be either 'add', 'remove', or 'replace'.")
        if (data["path"] is None or not isinstance(data["path"], str) or not data["path"].strip()):
            logger.warning("could not change host {} because the path was invalid: {}".format(fqdn, data["path"]))
            raise BadRequest("Invalid PATCH data. The 'path' field must contain a valid path to patch.")
        if (data["value"] is None or not isinstance(data["value"], dict)):
            logger.warning("could not change host {} because the value was invalid: {}".format(fqdn, data["value"]))
            raise BadRequest("Invalid PATCH data. The 'value' field must contain data to patch.")

        # we only support patching the assignments array
        if (data["path"] != "/assignments"):
            logger.warning("could not change host {} because the path was not supported: {}".format(fqdn, data["path"]))
            raise BadRequest("Unable to PATCH the path {}.".format(data["path"]))

        if (data["op"] == "add"):
            value = data["value"]
            process_name = value.get("name")
            process_environment = value.get("environment")

            if (process_name is None or not isinstance(process_name, str) or not process_name.strip()):
                logger.warning("could not add process to host {} because either the process name was missing".format(fqdn))
                raise BadRequest("No process name given.")
            if (process_environment is None or not isinstance(process_environment, str) or not process_environment.strip()):
                logger.warning("could not add process to host {} because either the process environment was missing".format(fqdn))
                raise BadRequest("No process environment given.")

            # make sure this is a valid process
            if (not q.is_valid_process(process_name, process_environment)):
                logger.warning("could not add process to host {} because no process was found with the name {} and environment {}".format(fqdn, process_name, process_environment))
                raise NotFound("No process found named {} with the environment {}.".format(process_name, process_environment))

            q.insert_host_assignment(fqdn, process_name, process_environment)
        elif (data["op"] == "remove"):
            value = data["value"]
            process_name = value.get("name")

            if (process_name is None or not process_name):
                logger.warning("could not add process to host {} because either the process name was missing".format(fqdn))
                raise BadRequest("No process name given.")

            # make sure this is a valid process
            if (not q.is_valid_process(process_name)):
                logger.warning("could not remove process from host {} because no process was found with the name {}".format(fqdn, process_name))
                raise NotFound("No process found named {}.".format(process_name))

            q.delete_host_assignment(fqdn, process_name)
        else:
            raise BadRequest("Unable to execute PATCH operation {} against {}.".format(data["op"], data["path"]))

        conn.commit()

        return make_response(jsonify({}), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


# enable or disable a process on a host
@v1.route("/processes/<name>", methods=["PATCH"])
@login_required
@validate_json_data
def change_process(name):
    # make a copy of the request data. this should be a valid python object
    # since our "validate_json_data" call cleaned it up.
    data = request.data

    # to help with debugging
    logger.debug("received process change request from {}: {}".format(current_user.source, data))

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # make sure the process is valid
        if (not q.is_valid_process(name)):
            logger.warning("could not change the process {} because it was not found".format(name))
            raise NotFound("No process found with the name {}.".format(name))

        # we need all of these fields
        if ("op" not in data or "path" not in data or "value" not in data):
            logger.warning("could not change process {} because the patch data was missing fields".format(name))
            raise BadRequest("Invalid PATCH data. Must include fields 'op', 'patch', and 'value'.")

        # make sure the fields look good
        if (data["op"] is None or not isinstance(data["op"], str) or not data["op"].strip() or data["op"] not in ["add", "remove", "replace"]):
            logger.warning("could not change process {} because the operation value was invalid: {}".format(name, data["op"]))
            raise BadRequest("Invalid PATCH data. The 'op' field must be either 'add', 'remove', or 'replace'.")
        if (data["path"] is None or not isinstance(data["path"], str) or not data["path"].strip()):
            logger.warning("could not change process {} because the path was invalid: {}".format(name, data["path"]))
            raise BadRequest("Invalid PATCH data. The 'path' field must contain a valid path to patch.")
        if (data["value"] is None or not isinstance(data["value"], dict)):
            logger.warning("could not change process {} because the value was invalid: {}".format(name, data["value"]))
            raise BadRequest("Invalid PATCH data. The 'value' field must contain data to patch.")

        # we only support patching the assignments array
        if (data["path"] != "/assignments"):
            logger.warning("could not change process {} because the path was not supported: {}".format(name, data["path"]))
            raise BadRequest("Unable to PATCH {}.".format(data["path"]))

        # we only support the "replace" operation
        if (data["op"] == "replace"):
            value = data["value"]
            fqdn = value.get("fqdn")
            disabled = value.get("disabled")

            if (fqdn is None or not isinstance(fqdn, str) or not fqdn.strip()):
                logger.warning("could not update process {} because the fqdn was missing".format(name))
                raise BadRequest("No fully qualified domain name given.")

            # make sure this is a valid fqdn
            if (not q.is_valid_host(fqdn)):
                logger.warning("could not update process {} because no host was found with the fqdn {}".format(name, fqdn))
                raise NotFound("No host found with the fully qualified domain name {}.".format(fqdn))

            # make sure our boolean is valid
            if (disabled is None):
                logger.warning("could not update process {} on {} because the value for disabled was invalid: {}".format(name, fqdn, disabled))
                raise NotFound("Invalid PATCH data. A value for disabled must be given.")

            # now convert it to a string and evaluate it
            disabled = str(disabled).strip().lower()
            if (disabled not in ["yes", "true", "no", "false"]):
                logger.warning("could not update process {} on {} because the value for disabled was invalid: {}".format(name, fqdn, disabled))
                raise NotFound("Invalid PATCH data. The value for disabled must be either 'yes', 'no', 'true', or 'false'.")

            q.update_process_disabled(fqdn, name, disabled in ["yes", "true"])
        else:
            raise BadRequest("Unable to execute PATCH operation {} against {}.".format(data["op"], data["path"]))

        conn.commit()

        return make_response(jsonify({}), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


@v1.route("/register", methods=["POST"])
@login_required
@validate_json_data
def register():
    # make a copy of the request data. this should be a valid python object
    # since our "validate_json_data" call cleaned it up.
    data = request.data

    # to help with debugging
    logger.debug("received registration request from {}: {}".format(current_user.source, data))

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        processes = data.get("processes")
        if (processes is not None):
            if (not isinstance(processes, list)):
                raise BadRequest("Processes must be provided as a list.")

            # add all of the processes back
            for index, process in enumerate(processes):
                register_process(process, index + 1)

        # clean up the transaction
        conn.commit()

        # return only that we succeeded
        return make_response(jsonify({}), 200)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise e
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass


def register_process(data, sort_order):
    # get the pieces that we need and validate some things as soon as possible
    process_name = data.get("name")
    if (process_name is None or not isinstance(process_name, str) or not process_name.strip()):
        raise BadRequest("The number {} process in the list has a name that is either undefined, empty, or not a string: {}".format(sort_order, process_name))
    process_environment = data.get("environment", "production")
    if (process_environment is None or not isinstance(process_environment, str) or not process_environment.strip()):
        raise BadRequest("The number {} process named '{}' has an environment that is either undefined, empty, or not a string: {}".format(sort_order, process_name, process_environment))

    process_type = data.get("type", "program")
    if (process_type not in ["program", "eventlistener"]):
        raise BadRequest("The process type for '{}' in '{}' must either be 'program' or 'eventlistener' and not '{}'.".format(process_name, process_environment, process_type))

    # get all of the process settings
    supervisor = data.get("supervisor", "").strip()  # this is the supervisord config
    schedule = data.get("schedule", "").strip() or None  # this should be NULL if no schedule

    # validate the schedule
    if (schedule is not None):
        try:
            CronTab(schedule)
        except ValueError:
            raise BadRequest("The schedule for '{}' in '{}' is not valid: {}".format(process_name, process_environment, schedule))

    # update the database with the new process details
    q.insert_process(process_name, process_environment, process_type, supervisor, schedule)

    monitors = data.get("monitoring", dict())
    default_contact = monitors.get("contact")
    state_monitor = monitors.get("state")
    daemon_monitor = monitors.get("daemon")
    keepalive_monitor = monitors.get("keepalive")
    log_monitor = monitors.get("logs")

    if (state_monitor is not None):
        try:
            contact = validate_contact(state_monitor.get("contact", default_contact))
            severity = validate_severity(state_monitor.get("severity"))
            q.insert_process_state_monitor(process_name, process_environment, contact, severity)
        except BadRequest as e:
            raise BadRequest("The state monitoring configuration for '{}' in '{}' is not valid: {}.".format(process_name, process_environment, e))

    if (daemon_monitor is not None):
        try:
            contact = validate_contact(daemon_monitor.get("contact", default_contact))
            severity = validate_severity(daemon_monitor.get("severity"))
            q.insert_process_daemon_monitor(process_name, process_environment, contact, severity)
        except BadRequest as e:
            raise BadRequest("The daemon monitoring configuration for '{}' in '{}' is not valid: {}.".format(process_name, process_environment, e))

    if (keepalive_monitor is not None):
        try:
            contact = validate_contact(keepalive_monitor.get("contact", default_contact))
            severity = validate_severity(keepalive_monitor.get("severity"))

            timeout = keepalive_monitor.get("timeout")
            if (timeout is None):
                raise BadRequest("missing timeout")
            try:
                timeout = int(timeout)
            except TypeError:
                raise BadRequest("timeout is invalid")
            if (timeout < 1 or timeout > 10080):
                raise BadRequest("timeout must be at least one minute and no longer than one week")

            q.insert_process_keepalive_monitor(process_name, process_environment, timeout, contact, severity)
        except BadRequest as e:
            raise BadRequest("The keepalive monitoring configuration for '{}' in '{}' is not valid: {}.".format(process_name, process_environment, e))

    if (log_monitor is not None):
        try:
            for stream in log_monitor:
                if (stream not in ["stdout", "stderr"]):
                    raise BadRequest("the only valid streams are 'stdout' and 'stderr'")

                for index, config in enumerate(log_monitor[stream]):
                    regex = config.get("regex")  # must exist
                    name = config.get("name")  # optional
                    stop = config.get("stop")  # optional
                    severity = config.get("severity")  # optional
                    contact = validate_contact(config.get("contact", default_contact))

                    # validate the regex
                    if (regex is None):
                        raise BadRequest("missing regex")
                    try:
                        re.compile(regex)
                    except re.error as e:
                        raise BadRequest(str(e))

                    # severity is optional
                    if (severity is not None):
                        severity = validate_severity(severity)

                    # if set to a true value then true, otherwise if it is
                    # missing or set to anything else then false
                    stop = (stop is not None and str(stop).lower() in ["yes", "true", "on", "1"])

                    q.insert_process_log_monitor(process_name, process_environment, stream, index, regex, stop, name, contact, severity)
        except BadRequest as e:
            raise BadRequest("The log monitoring configuration for '{}' in '{}' is not valid: {}.".format(process_name, process_environment, e))


def validate_contact(contact):
    if (contact is None):
        raise BadRequest("missing contact")
    return contact


def validate_severity(severity):
    if (severity is None):
        raise BadRequest("missing severity")
    if (severity != str(severity)):
        try:
            severity = int(severity)
        except TypeError:
            raise BadRequest("severity is invalid")
    severity = str(severity).strip().upper()
    if (severity not in ["1", "2", "3", "4", "5", "OK"]):
        raise BadRequest("severity must be either 1, 2, 3, 4, 5, or OK")
    return severity
