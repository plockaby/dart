from ....app import db_client
from ....validators import validate_json_data
from . import v1
from . import queries as q
from flask import jsonify, make_response, request
from flask_login import login_required
from werkzeug.exceptions import BadRequest


@v1.route("/assigned/<fqdn>", methods=["GET"])
@login_required
def get_assigned_processes(fqdn):
    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # returns assignments and all configurations
        assignments = q.get_assigned_processes(fqdn)

        # clean up the transaction
        conn.commit()

        return make_response(jsonify(list(assignments)), 200)
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


@v1.route("/active/<fqdn>", methods=["POST"])
@login_required
@validate_json_data
def post_active_processes(fqdn):
    # to help with debugging, data will look like this:
    #  [
    #       {
    #           'now': 1556774041,
    #           'name': 'cassandra-node-repair',
    #           'group': 'cassandra-node-repair',
    #           'description': 'May 01 10:10 PM',
    #           'pid': 0,
    #           'start': 1556773824,
    #           'stop': 1556773825,
    #           'exitstatus': 0,
    #           'spawnerr': '',
    #           'statename': 'EXITED',
    #           'state': 100,
    #           'logfile': '/data/logs/supervisor/cassandra-node-repair.log',
    #           'stdout_logfile': '/data/logs/supervisor/cassandra-node-repair.log',
    #           'stderr_logfile': '/data/logs/supervisor/cassandra-node-repair.err',
    #       }
    #  ]

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # keep a list of the names that are active on this host. we are going
        # to delete anything that is not on this list.
        active = []

        # make sure that we have a valid host
        q.insert_fqdn(fqdn)

        # then insert them all
        for process in request.data:
            # make sure that we have a name and a state
            if (process.get("name") is None):
                raise BadRequest("The DartAPI received invalid data.")
            if (process.get("statename") is None):
                raise BadRequest("The DartAPI received invalid data.")

            active.append(process["name"])
            q.insert_active(
                fqdn,
                process.get("name"),
                process.get("statename"),
                process.get("start"),
                process.get("stop"),
                process.get("stdout_logfile"),
                process.get("stderr_logfile"),
                process.get("pid"),
                process.get("exitstatus"),
                process.get("description"),
                process.get("spawnerr"),
            )

        # clean up things that don't exist anymore
        q.delete_active(fqdn, active)

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


@v1.route("/pending/<fqdn>", methods=["POST"])
@login_required
@validate_json_data
def post_pending_processes(fqdn):
    # to help with debugging, data will look like this:
    # {
    #     'added': ['dart-api-web'],
    #     'changed': [],
    #     'removed': []
    # }

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # keep a list of the names that are pending on this host. we are going
        # to delete anything that is not on this list.
        pending = []

        # make sure that we have a valid host
        q.insert_fqdn(fqdn)

        # then insert them all again
        for process in request.data.get("added", []):
            pending.append(process)
            q.insert_pending(fqdn, process, "added")
        for process in request.data.get("changed", []):
            pending.append(process)
            q.insert_pending(fqdn, process, "changed")
        for process in request.data.get("removed", []):
            pending.append(process)
            q.insert_pending(fqdn, process, "removed")

        # clean up things that don't exist anymore
        q.delete_pending(fqdn, pending)

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


@v1.route("/state/<fqdn>/<process>", methods=["POST"])
@login_required
@validate_json_data
def post_state(fqdn, process):
    # to help with debugging, data will look like this:
    # {
    #      'description': 'May 01 10:10 PM',
    #      'pid': 0,
    #      'stop': 1556773825,
    #      'exitstatus': 0,
    #      'spawnerr': '',
    #      'now': 1556773826,
    #      'group': 'cassandra-node-repair',
    #      'name': 'cassandra-node-repair',
    #      'statename': 'EXITED',
    #      'start': 1556773824,
    #      'state': 100,
    #      'logfile': '/data/logs/supervisor/cassandra-node-repair.log',
    #      'stdout_logfile': '/data/logs/supervisor/cassandra-node-repair.log'
    #      'stderr_logfile': '/data/logs/supervisor/cassandra-node-repair.err',
    #  }

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # make sure that we have a valid host
        q.insert_fqdn(fqdn)

        # make sure that we have a name and a state
        if (request.data.get("name") is None):
            raise BadRequest("The DartAPI received invalid data.")
        if (request.data.get("statename") is None):
            raise BadRequest("The DartAPI received invalid data.")

        # send it to the database
        q.insert_active(
            fqdn,
            request.data.get("name"),
            request.data.get("statename"),
            request.data.get("start"),
            request.data.get("stop"),
            request.data.get("stdout_logfile"),
            request.data.get("stderr_logfile"),
            request.data.get("pid"),
            request.data.get("exitstatus"),
            request.data.get("description"),
            request.data.get("spawnerr"),
        )

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


@v1.route("/probe/<fqdn>", methods=["POST"])
@login_required
@validate_json_data
def post_probe(fqdn):
    # to help with debugging, data will look like this:
    # {
    #      'boot_time': 1536093182,
    #      'kernel': 'Linux-3.10.0-862.6.3.el7.x86_64-x86_64-with-centos-7.6.1810-Core',
    #  }

    conn = None
    try:
        conn = db_client.conn()
        conn.autocommit = False

        # save default information
        q.insert_host(
            fqdn,
            request.data.get("booted"),
            request.data.get("kernel"),
        )

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
