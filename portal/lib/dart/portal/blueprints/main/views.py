from ...app import cache
from ... import requests as r
from . import main
from flask import render_template
from datetime import datetime
import dart.common
import dart.common.html


@main.route("/")
def index():
    hosts = r.select_hosts()
    processes = r.select_processes()
    now = datetime.now()

    return render_template(
        "index.html",
        hosts=hosts,
        processes=processes,
        now=now
    )


@main.route("/hosts")
def hosts():
    # shows a list of all hosts
    return render_template("hosts.html")


@main.route("/host/<string:fqdn>")
def host(fqdn):
    @cache.cached(timeout=1, key_prefix="api/host/{}".format(fqdn))
    def select():
        return r.select_host(fqdn)  # returns None if no host
    host = select()

    if (host is None or host["polled"] is None):
        return render_template(
            "host.html",
            fqdn=fqdn,
            error="No host named {} is managed by dart.".format(dart.common.html.sanitize(fqdn)),
            ignore=dart.common.PROCESSES_TO_IGNORE,
        )

    return render_template(
        "host.html",
        fqdn=fqdn,
        host=host,
        ignore=dart.common.PROCESSES_TO_IGNORE,
    )


@main.route("/processes")
def processes():
    return render_template("processes.html", ignore=dart.common.PROCESSES_TO_IGNORE)


@main.route("/process/<string:name>")
def process(name):
    @cache.cached(timeout=1, key_prefix="api/process/{}".format(name))
    def select():
        return r.select_process(name)  # returns None if no process
    process = select()

    if (process is None):
        return render_template(
            "process.html",
            name=name,
            error="No process named {} is configured in dart.".format(dart.common.html.sanitize(name)),
            ignore=dart.common.PROCESSES_TO_IGNORE,
        )

    return render_template(
        "process.html",
        name=name,
        process=process,
        ignore=dart.common.PROCESSES_TO_IGNORE,
    )


@main.route("/register")
def register():
    return render_template("register.html")
