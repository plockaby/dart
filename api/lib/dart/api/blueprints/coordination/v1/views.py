from ....app import logger
from ....app import settings_manager
from . import v1
from flask import jsonify, make_response
from flask_login import login_required
import socket
import ssl
import json


@v1.route("/start/<string:fqdn>/<string:process_name>", methods=["POST"])
@login_required
def start(fqdn, process_name):
    logger.info("sending start command to {} on {}".format(fqdn, process_name))
    send_command(fqdn, "start", process_name)
    return make_response(jsonify({}), 200)


@v1.route("/stop/<string:fqdn>/<string:process_name>", methods=["POST"])
@login_required
def stop(fqdn, process_name):
    logger.info("sending stop command to {} on {}".format(fqdn, process_name))
    send_command(fqdn, "stop", process_name)
    return make_response(jsonify({}), 200)


@v1.route("/restart/<string:fqdn>/<string:process_name>", methods=["POST"])
@login_required
def restart(fqdn, process_name):
    logger.info("sending restart command to {} on {}".format(fqdn, process_name))
    send_command(fqdn, "restart", process_name)
    return make_response(jsonify({}), 200)


@v1.route("/update/<string:fqdn>/<string:process_name>", methods=["POST"])
@login_required
def update(fqdn, process_name):
    logger.info("sending update command to {} on {}".format(fqdn, process_name))
    send_command(fqdn, "update", process_name)
    return make_response(jsonify({}), 200)


@v1.route("/reread/<string:fqdn>", methods=["POST"])
@login_required
def reread(fqdn):
    logger.info("sending reread command to {}".format(fqdn))
    send_command(fqdn, "reread")
    return make_response(jsonify({}), 200)


@v1.route("/rewrite/<string:fqdn>", methods=["POST"])
@login_required
def rewrite(fqdn):
    logger.info("sending rewrite command to {}".format(fqdn))
    send_command(fqdn, "rewrite")
    return make_response(jsonify({}), 200)


def send_command(fqdn, action, process=None):
    ctx = ssl.SSLContext()
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True

    settings = settings_manager.get("coordination", {})
    ca = settings.get("ca")
    key = settings.get("key")
    name = settings.get("name")
    port = settings.get("port")
    logger.debug("connecting to {}:{} as {} using {} verified against {}".format(fqdn, port, name, key, ca))

    # we must validate the remote side against the UWCA
    ctx.load_verify_locations(ca)

    # we will present this as the client certificate for the connection
    ctx.load_cert_chain(key)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # we expect the remote side to identify itself as "dart.s.uw.edu"
        with ctx.wrap_socket(sock, server_hostname=name) as ssock:
            ssock.connect((fqdn, port))

            if (process is None):
                logger.debug("connected to {}, sending {}".format(fqdn, action))
                ssock.sendall((json.dumps({"action": action}) + "\n").encode())
            else:
                logger.debug("connected to {}, sending {} to {}".format(fqdn, action, process))
                ssock.sendall((json.dumps({"action": action, "process": process}) + "\n").encode())
