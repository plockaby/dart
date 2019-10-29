from . import main
from . import queries as q
from flask import render_template
from datetime import datetime
import dart.common
import dart.common.html


@main.route("/")
def index():
    hosts = q.select_hosts()
    processes = q.select_processes()
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


@main.route("/host/<fqdn>")
def host(fqdn):
    host = q.select_host(fqdn)  # returns None if no host

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


@main.route("/process/<name>")
def process(name):
    process = q.select_process(name)  # returns None if no process

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
    pass
