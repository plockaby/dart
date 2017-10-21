from flask import render_template, request, jsonify
from . import main
from datetime import datetime
import dart.common
import dart.common.query as q
import dart.common.exceptions


@main.route("/")
def index():
    # NOTE: do not be tempted to put lots of dart alarms or events or
    # configuration problems to fix here on the home page. things that should
    # be fixed should be sent to the event management system where there are
    # more robust processes for viewing, triaging, and managing those problems.
    hosts = q.hosts()
    processes = q.processes()
    now = datetime.utcnow()

    # remove hosts that are not managed by dart
    hosts = {key: value for key, value in hosts.items() if value["checked"] is not None}

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
    if (not q.is_valid_host(fqdn)):
        return render_template(
            "host.html",
            fqdn=fqdn,
            error="No host named {} is managed by dart.".format(fqdn),
        )

    # shows information about one host, similar to "dart host" command
    host = q.host(fqdn)
    tags = q.host_tags(fqdn)

    return render_template(
        "host.html",
        fqdn=fqdn,
        host=host,
        tags=tags,
        ignore=dart.common.PROCESSES_TO_IGNORE
    )


@main.route("/processes")
def processes():
    # shows a list of all processes
    return render_template("processes.html", ignore=dart.common.PROCESSES_TO_IGNORE)


@main.route("/process/<process>")
def process(process):
    if (not q.is_valid_process(process)):
        return render_template(
            "process.html",
            process=process,
            error="No process named {} is configured in dart.".format(process),
        )

    # shows information about one process, similar to "dart process" command
    configurations = q.process(process)

    # get monitoring information from cassandra
    daemon_monitoring = q.process_daemon_monitoring_configuration(process)
    state_monitoring = q.process_state_monitoring_configuration(process)
    log_monitoring = q.process_log_monitoring_configurations(process)

    return render_template(
        "process.html",
        process=process,
        configurations=configurations,
        daemon_monitoring=daemon_monitoring,
        state_monitoring=state_monitoring,
        log_monitoring=log_monitoring,
        ignore=dart.common.PROCESSES_TO_IGNORE
    )


@main.route("/autocomplete/process")
def autocomplete_process():
    search = request.args.get("q")
    results = []

    # make the search case insensitive
    if (search):
        search = search.lower()

    # process names, sorted
    processes = sorted(list(q.processes().keys()))

    # filter on a search field, if there is one
    # either way, only return 10 results
    for process in processes:
        if (len(results) < 10 and (not search or process.startswith(search))):
            results.append(process)

    return jsonify(dict(results=results))


@main.route("/autocomplete/environment")
def autocomplete_environment():
    search = request.args.get("q")
    process = request.args.get("process")
    results = []

    # make the search case insensitive
    if (search):
        search = search.lower()

    # if we don't have a process name then we can't do anything
    if (process):
        # environment names, sorted
        environments = sorted(list(q.process(process).keys()))

        # filter on a search field, if there is one
        # either way, only return 10 results
        for environment in environments:
            if (len(results) < 10):
                if (not search or environment.startswith(search)):
                    results.append(environment)
            else:
                break

    return jsonify(dict(results=results))


@main.route("/autocomplete/fqdn")
def autocomplete_fqdn():
    search = request.args.get("q")
    results = []

    # make the search case insensitive
    if (search):
        search = search.lower()

    # host names, sorted, filtered to only those that are dart managed
    fqdns = sorted([key for key, value in q.hosts().items() if value["checked"] is not None])

    # filter on a saerch field, if there is one
    # either way, only return 10 results
    for fqdn in fqdns:
        if (len(results) < 10):
            if (not search or fqdn.startswith(search)):
                results.append(fqdn)
        else:
            break

    return jsonify(dict(results=results))
