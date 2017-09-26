import cassandra.query
from . import exceptions


# this should be set before this thing can be used. to avoid problems with
# thread safety, this should be set once, immediately after the session is
# created. from there, the method that you assign this to should handle any
# thread safety issues.
session = None


# this returns the correct form of the session depending on whether it is a
# function that returns a session or just a session object itself
def __get_session():
    return session() if callable(session) else session


def is_valid_host(fqdn):
    """
        Given a fully qualified domain name this will return True or False
        depending on whether it is the name of a host controlled by dart.
    """
    s = __get_session()

    query = cassandra.query.SimpleStatement("""
        SELECT fqdn
        FROM dart.probe
        WHERE fqdn = %s
    """)
    rows = s.execute(query, (fqdn,))
    if (sum(1 for _ in rows)):
        return True

    return False


def is_valid_process(process, environment=None):
    """
        Given a process name and an optional environment this will return True
        or False depending on whether it is a valid process. A "valid process"
        is any process that is either configured in dart but not necessarily on
        a host or is active or pending on a host but not necessarily configured
        in dart.
    """
    s = __get_session()

    # if we have a dart configuration for it then it is a valid process
    query = cassandra.query.SimpleStatement("""
        SELECT process, environment
        FROM dart.configured
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        if (environment is None):
            return True
        else:
            if (row["environment"] == environment):
                return True

    # if we were given an environment and we didn't match above then the
    # process is definitely not valid
    if (environment is not None):
        return False

    # if we don't have a configuration but it is active then it is a valid process
    query = cassandra.query.SimpleStatement("""
        SELECT process
        FROM dart.configured_active
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    if (sum(1 for _ in rows)):
        return True

    # if we don't have a configuration and it is not active then finally just
    # check to see if it is pending. those would be processes that we are trying
    # to remove, maybe?
    query = cassandra.query.SimpleStatement("""
        SELECT process
        FROM dart.configured_pending
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    if (sum(1 for _ in rows)):
        return True

    return False


def is_process_assigned_to_host(fqdn, process, environment=None):
    """
        Given a fully qualified domain name, a process name, and an optional
        environment this will return True or False depending on whether the
        process is assigned to the host with the given fully qualified domain
        name.
    """
    s = __get_session()

    query = cassandra.query.SimpleStatement("""
        SELECT process, environment
        FROM dart.assignment
        WHERE fqdn = %s
          AND process = %s
    """)
    rows = s.execute(query, (fqdn, process))
    for row in rows:
        if (environment is None):
            return True
        else:
            if (row["environment"] == environment):
                return True

    return False


def hosts():
    """
        This returns all hosts known to dart. The result is a dict where the
        key is the fully qualified domain name and the value is another dict
        containing a handful of details about the host including: when it was
        last checked, the number of processes configured on the host, the number
        of processes that are pending changes on the host, and the number of
        processes that are in an error state on the host. Here are some details
        on specific fields:

        * checked - when the host's configuration was last checked by dart
        * total - the number of processes active on the host
        * running - the number of processes that are active and running
        * stopped - the number of processes that are not running but not failed
        * failed - the number of processes in a failed state
        * pending - the number of processes that have pending configuration
          changes
        * disabled - the number of processes that are disabled
        * assigned - the number of processes that are assigned
    """
    s = __get_session()

    # start the list with hosts that we are probing
    hosts = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            checked
        FROM dart.probe
    """)
    rows = s.execute(query)
    for row in rows:
        hosts[row["fqdn"]] = dict(
            fqdn=row["fqdn"],
            checked=row["checked"],
            total=0,
            running=0,
            stopped=0,
            failed=0,
            pending=0,
            assigned=0,
            disabled=0,
        )

    # find the state of each process on each host. we don't care what the
    # process is, just its state, so only fetch the fields that we need.
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            status
        FROM dart.configured_active
    """)
    rows = s.execute(query)
    for row in rows:
        hosts[row["fqdn"]]["total"] += 1
        if (row["status"] == "RUNNING"):
            hosts[row["fqdn"]]["running"] += 1
        if (row["status"] in ["STARTING", "STOPPED", "STOPPING", "EXITED"]):
            hosts[row["fqdn"]]["stopped"] += 1
        if (row["status"] in ["BACKOFF", "FATAL", "UNKNOWN"]):
            hosts[row["fqdn"]]["failed"] += 1

    # find how many are pending on each host. every row represents one pending
    # change to a process. we don't care what the change is as we just want to
    # count them up so don't fetch the fields that we don't need.
    query = cassandra.query.SimpleStatement("""
        SELECT fqdn
        FROM dart.configured_pending
    """)
    rows = s.execute(query)
    for row in rows:
        hosts[row["fqdn"]]["pending"] += 1

    # find out how many processes are assigned and disabled
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            disabled
        FROM dart.assignment
    """)
    rows = s.execute(query)
    for row in rows:
        hosts[row["fqdn"]]["assigned"] += 1
        if (row["disabled"]):
            hosts[row["fqdn"]]["disabled"] += 1

    return hosts


def host(fqdn):
    """
        When given a fully qualified domain name this will return a dict
        containing details about the host with that fully qualified domain
        name. No checks are performed to see if the fully qualified domain name
        is the name of a valid host. If the fully qualified domain name is not
        the name of a valid host then this will return an empty dict.
    """
    s = __get_session()

    probe = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            checked,
            system_started,
            kernel
        FROM dart.probe
        WHERE fqdn = %s
    """)
    rows = s.execute(query, (fqdn,))
    # this should just return one row
    for row in rows:
        probe = row

    return probe


def host_active(fqdn):
    """
        Given a fully qualified domain name this will return a dict containing
        all processes that are actively running on the host with that fully
        qualified domain name. The key to the dict is the name of the process
        and the value is another dict containing the name of the process as
        well as the process's status (e.g. RUNNING, STOPPED, etc.), the
        process's description, and whether the process is enabled or disabled.
        No checks are performed to see if the fully qualified domain name is
        the name of a valid host. In both the case where the fully qualified
        domain name is not the name of a valid host and the case where the host
        has no active processes this will return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            status,
            started,
            stopped,
            error,
            description
        FROM dart.configured_active
        WHERE fqdn = %s
    """)
    rows = s.execute(query, (fqdn,))
    for row in rows:
        details[row["process"]] = row
        details[row["process"]]["environment"] = None
        details[row["process"]]["disabled"] = False

    # now see if the process is enabled
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            environment,
            disabled
        FROM dart.assignment
        WHERE fqdn = %s
          AND process = %s
    """)
    for process in details:
        futures.append(s.execute_async(future_query, [fqdn, process]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["process"]]["environment"] = row["environment"]
            details[row["process"]]["disabled"] = row["disabled"] or False

    # get any daemon information for these processes. if this is supposed to be
    # a daemon we want to know that, just like we want to know if it is a
    # scheduled job.
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT process
        FROM dart.process_daemon_monitor
        WHERE process = %s
          AND environment = %s
    """)
    for process in details:
        if (details[process]["environment"]):
            futures.append(s.execute_async(future_query, [process, details[process]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["process"]]["daemon"] = True

    return details


def host_pending(fqdn):
    """
        Given a fully qualified domain name this will return a dict containing
        all processes that are pending changes on the host with that fully
        qualified domain name. The key to the dict is the name of the process
        and the value is another dict containing the name of the process, the
        process's status (e.g. changed, added, removed), and whether the
        process is enbaled or disabled. No checks are performed to see if the
        fully qualified domain name is the name of a valid host. In both the
        case where the fully qualified domain name is not the name of a valid
        host and the case where the host has no pending processes this will
        return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            status
        FROM dart.configured_pending
        WHERE fqdn = %s
    """)
    rows = s.execute(query, (fqdn,))
    for row in rows:
        details[row["process"]] = row
        details[row["process"]]["disabled"] = False

    # now see if the process is enabled
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            disabled
        FROM dart.assignment
        WHERE fqdn = %s
          AND process = %s
    """)
    for process in details:
        futures.append(s.execute_async(future_query, [fqdn, process]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["process"]]["disabled"] = row["disabled"] or False

    return details


def host_assigned(fqdn):
    """
        Given a fully qualified domain name this will return a dict containing
        all processes that are assigned to the host with that fully qualified
        domain name. The key to the dict is the name of the process and the
        value is another dict containing the name of the process, the process
        environment that is assigned to the host, the process's configuration,
        the process's schedule, if any, plus the time at which the process will
        next start, whether the process should be a daemon, and whether the
        process is enabled or disabled. No checks are performed to see if the
        fully qualified domain name is the name of a valid host. In both the
        case where the fully qualified domain name is not the name of a valid
        host and the case where the host has no assigned processes this will
        return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            environment,
            disabled
        FROM dart.assignment
        WHERE fqdn = %s
    """)
    rows = s.execute(query, (fqdn,))
    for row in rows:
        details[row["process"]] = dict(
            process=row["process"],
            environment=row["environment"],
            disabled=row["disabled"],
            configuration=None,
            schedule=None,
            daemon=False,
        )

    # get any configurations for these processes. only one environment can be
    # assigned to a host so we query on environment but we don't key on it in
    # our dict. this is used by the dart agent when it writes configurations
    # to a host.
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            configuration
        FROM dart.configured
        WHERE process = %s
          AND environment = %s
    """)
    for process in details:
        futures.append(s.execute_async(future_query, [process, details[process]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["process"]]["configuration"] = row["configuration"]

    # get any schedules for these processes. only one environment can be
    # assigned to a host so we query on environment but we don't key on it
    # in our dict.
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            schedule
        FROM dart.schedule
        WHERE process = %s
          AND environment = %s
    """)
    for process in details:
        futures.append(s.execute_async(future_query, [process, details[process]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["process"]]["schedule"] = row["schedule"]
            try:
                import datetime
                from crontab import CronTab
                crontab = CronTab(row["schedule"])
                now = datetime.datetime.utcnow()
                details[row["process"]]["starts"] = now + datetime.timedelta(seconds=(int(crontab.next(default_utc=False)) + 1))
            except ValueError as e:
                pass

    # get any daemon information for these processes. if this is supposed to be
    # a daemon we want to know that, just like we want to know if it is a
    # scheduled job.
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT process
        FROM dart.process_daemon_monitor
        WHERE process = %s
          AND environment = %s
    """)
    for process in details:
        futures.append(s.execute_async(future_query, [process, details[process]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["process"]]["daemon"] = True

    return details


def host_tags(fqdn=None):
    """
        Given no arguments this will return a dict containing all hosts and
        their tags. The key to the dict is the fqdn and the value is an array
        of tags. If a host has no tags then it will not be in the dict.

        Given a fully qualified domain name then this will return an array of
        the tags assigned to the host with that fully qualified domain name. No
        checks are performed to see if the fully qualified domain name is the
        name of a valid host. In both the case where the fully qualified domain
        name is not the name of a valid host and the case where the host has no
        tags this will return an empty list.
    """
    s = __get_session()

    if (fqdn is not None):
        details = []
        query = cassandra.query.SimpleStatement("""
            SELECT tag
            FROM dart.host_tag
            WHERE fqdn = %s
        """)
        rows = s.execute(query, (fqdn,))
        for row in rows:
            details.append(row["tag"])

        return details
    else:
        results = dict()
        query = cassandra.query.SimpleStatement("""
            SELECT
                tag,
                fqdn
            FROM dart.host_tag
        """)
        rows = s.execute(query)
        for row in rows:
            if (row["tag"] not in results):
                results[row["tag"]] = []
            results[row["tag"]].append(row["fqdn"])

        return results


def add_host_tag(fqdn, tag):
    """
        Given a fully qualified domain name and a tag this will assign the
        given tag to the host with that fully qualified domain name. If the tag
        is invalid then this will raise the DartInvalidTagException exception.
        If the fully qualified domain name is not the name of a valid host then
        this will raise the DartHostDoesNotExistException exception. If the tag
        is already assigned to the host then this is a noop.
    """
    import string
    if (True in [c in tag for c in string.whitespace]):
        raise exceptions.DartInvalidTagException("tags cannot contain any whitespace")

    if (not is_valid_host(fqdn)):
        raise exceptions.DartHostDoesNotExistException("{} does not exist".format(fqdn))

    s = __get_session()
    query = cassandra.query.SimpleStatement("""
        INSERT INTO dart.host_tag
        (fqdn, tag) VALUES (%s, %s)
    """)
    s.execute(query, (fqdn, tag))


def remove_host_tag(fqdn, tag):
    """
        Given a fully qualified domain name and a tag this will remove the
        given tag from the host with that fully qualified domain name. If the
        fully qualified domain name is not the name of a valid host then this
        will raise the DartHostDoesNotExistException exception. If the tag is
        not assigned to the host then this is a noop.
    """
    if (not is_valid_host(fqdn)):
        raise exceptions.DartHostDoesNotExistException("{} does not exist".format(fqdn))

    s = __get_session()
    query = cassandra.query.SimpleStatement("""
        DELETE FROM dart.host_tag
        WHERE fqdn = %s
          AND tag = %s
    """)
    s.execute(query, (fqdn, tag))


def processes():
    """
        This returns all processes known to dart. This includes processed that
        are active whether or not they are configured and those configured
        whether or not they are active as well as those that are pending
        changes on any host. The result is a dict where the key is the name of
        the process and the value is another dict containing a handful of
        details about the process including: the set of hosts on which the
        process is active, the set of hosts on which the process has a
        pending change, the set of hosts on which the process is assigned, as
        well as the number of hosts on which the process is configured,
        assigned, disabled, active, failed, or pending changes. Here are some
        details on specific fields:

        * configured - the number of configurations that this process has
        * assigned - the number of hosts to which this process is assigned
        * disabled - the number of hosts on which this process is disabled
        * active - the number of hosts on which this process is actively
          running
        * failed - the number of hosts on which this process is currently
          failing
        * pending - the number of hosts on which this process has pending
          configuration changes
    """
    s = __get_session()

    processes = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            process,
            status
        FROM dart.configured_active
    """)
    rows = s.execute(query)
    for row in rows:
        if (row["process"] not in processes):
            processes[row["process"]] = dict(
                process=row["process"],
                active_hosts=set(),
                pending_hosts=set(),
                assigned_hosts=set(),
                configured=0,
                assigned=0,
                disabled=0,
                active=0,
                failed=0,
                pending=0,
            )

        # count up how many times this process appears
        processes[row["process"]]["active"] += 1
        if (row["status"] in ["BACKOFF", "FATAL", "UNKNOWN"]):
            processes[row["process"]]["failed"] += 1

        # record all of the hosts that this is active on
        processes[row["process"]]["active_hosts"].add(row["fqdn"])

    # get how many hosts the process has pending changes on
    query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            fqdn,
            status
        FROM dart.configured_pending
    """)
    rows = s.execute(query)
    for row in rows:
        if (row["process"] not in processes):
            processes[row["process"]] = dict(
                process=row["process"],
                active_hosts=set(),
                pending_hosts=set(),
                assigned_hosts=set(),
                configured=0,
                assigned=0,
                disabled=0,
                active=0,
                failed=0,
                pending=0,
            )

        processes[row["process"]]["pending"] += 1

        # record all of the hosts that this is pending on but only if it
        # is a pending "add". a pending change or removal is uninteresting.
        # it is uninteresting because if it is "changed" or "removed" then
        # it is already active and the "active not assigned" alarm will
        # raise an alert and we don't need multiple alerts.
        if (row["status"] not in ["changed", "removed"]):
            processes[row["process"]]["pending_hosts"].add(row["fqdn"])

    # get how many hosts the process is assigned to
    query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            fqdn,
            disabled
        FROM dart.assignment
    """)
    rows = s.execute(query)
    for row in rows:
        if (row["process"] not in processes):
            processes[row["process"]] = dict(
                process=row["process"],
                active_hosts=set(),
                pending_hosts=set(),
                assigned_hosts=set(),
                configured=0,
                assigned=0,
                disabled=0,
                active=0,
                failed=0,
                pending=0,
            )

        processes[row["process"]]["assigned"] += 1
        if (row["disabled"]):
            processes[row["process"]]["disabled"] += 1

        # record all of the hosts that this is assigned to
        processes[row["process"]]["assigned_hosts"].add(row["fqdn"])

    # get how many configurations this process has
    query = cassandra.query.SimpleStatement("""
        SELECT process
        FROM dart.configured
    """)
    rows = s.execute(query)
    for row in rows:
        if (row["process"] not in processes):
            processes[row["process"]] = dict(
                process=row["process"],
                active_hosts=set(),
                pending_hosts=set(),
                assigned_hosts=set(),
                configured=0,
                assigned=0,
                disabled=0,
                active=0,
                failed=0,
                pending=0,
            )

        processes[row["process"]]["configured"] += 1

    return processes


def process(process):
    """
        Given a valid process name this will return a dict containing details
        about that process. The key to the dict is the environment for which
        the details pertain. The value is the supervisor configuration for the
        process in the given environment. No checks are performed to see if the
        process name is valid. If the process name is not valid then this will
        return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            environment,
            configuration
        FROM dart.configured
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        if (row["environment"] not in details):
            details[row["environment"]] = dict(configuration=None, schedule=None)
        details[row["environment"]]["configuration"] = row["configuration"]

    query = cassandra.query.SimpleStatement("""
        SELECT
            environment,
            schedule
        FROM dart.schedule
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        if (row["environment"] not in details):
            details[row["environment"]] = dict(configuration=None, schedule=None)
        details[row["environment"]]["schedule"] = row["schedule"]

    return details


def process_log_monitoring_configurations(process):
    """
        Given a process name this will return a dict with the log monitoring
        configuration for the process. The key to the dict is the name of the
        environment for which the configuration pertains. The value is an array
        of dicts containing the log monitoring configuration in sorted order.
        No checks are performed to see if the process name is valid. In both
        the case where the process name is not valid and the case where the
        process has no log monitoring configuration this will return an empty
        dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            environment,
            id,
            stream,
            regex,
            name,
            contact,
            severity,
            stop
        FROM dart.process_log_monitor
        WHERE process = %s
        ALLOW FILTERING
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        if (row["environment"] not in details):
            details[row["environment"]] = []
        details[row["environment"]].append(row)

    # now sort the log monitoring details because the log monitoring
    # configuration only makes sense when sorted.
    for environment in details:
        details[environment] = sorted(details[environment], key=lambda x: (x["stream"], x["id"]))

    return details


def process_state_monitoring_configuration(process):
    """
        Given a process name this will return a dict with the state monitoring
        configuration for the process. The key to the dict is the name of the
        environment for which the configuration pertains. The value is a dict
        containing the state monitoring configuration. No checks are performed
        to see if the process name is valid. In both the case where the process
        name is not valid and the case where the process has no state
        monitoring configuration this will return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            environment,
            contact,
            severity
        FROM dart.process_state_monitor
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        details[row["environment"]] = row

    return details


def process_daemon_monitoring_configuration(process):
    """
        Given a process name this will return a dict with the daemon monitoring
        configuration for the process. The key to the dict is the name of the
        environment for which the configuration pertains. The value is a dict
        containing the daemon monitoring configuration. No checks are performed
        to see if the process name is valid. In both the case where the process
        name is not valid and the case where the process has no daemon
        monitoring configuration this will return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            environment,
            contact,
            severity
        FROM dart.process_daemon_monitor
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        details[row["environment"]] = row

    return details


def process_active(process):
    """
        Given a process name this will return a dict containing all of the
        hosts on which the process is active. The key to the dict is the fully
        qualified domain name of the host on which the process is active. The
        value is a dict containing the status of the process on that host, a
        description, and whether or not the process is disabled on the host. No
        checks are performed to see if the process name is valid. In both the
        case where the process name is not valid and the case where the process
        is not active on any hosts this will return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            status,
            started,
            stopped,
            error,
            description
        FROM dart.configured_active
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        details[row["fqdn"]] = row
        details[row["fqdn"]]["disabled"] = False
        details[row["fqdn"]]["environment"] = None

    # now see if the process is enabled
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            environment,
            disabled
        FROM dart.assignment
        WHERE fqdn = %s
          AND process = %s
    """)
    for fqdn in details:
        futures.append(s.execute_async(future_query, [fqdn, process]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["fqdn"]]["disabled"] = row["disabled"] or False
            details[row["fqdn"]]["environment"] = row["environment"]

            if (row["environment"]):
                # find the daemon state for this process
                subquery = cassandra.query.SimpleStatement("""
                    SELECT process
                    FROM dart.process_daemon_monitor
                    WHERE process = %s
                      AND environment = %s
                """)
                subrows = s.execute(subquery, (process, row["environment"]))
                for subrow in subrows:
                    # this should only return one row
                    details[row["fqdn"]]["daemon"] = True

    return details


def process_pending(process):
    """
        Given a process name this will return a dict containing all of the
        hosts on which the process has pending changes. The key to the dict is
        the fully qualified domain name of the host on which the process is
        pending. The value is a dict containing the status of the process on
        that host and whether or not the process is disabled on that host. No
        checks are performed to see if the process name is valid. In both the
        case where the process name is not valid and the case where the process
        is not active on any hosts this will return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            status
        FROM dart.configured_pending
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        details[row["fqdn"]] = row
        details[row["fqdn"]]["disabled"] = False

    # now see if the process is enabled
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            disabled
        FROM dart.assignment
        WHERE fqdn = %s
          AND process = %s
    """)
    for fqdn in details:
        futures.append(s.execute_async(future_query, [fqdn, process]))

    for future in futures:
        rows = future.result()
        for row in rows:
            details[row["fqdn"]]["disabled"] = row["disabled"] or False

    return details


def process_assigned(process):
    """
        Given a process name this will return a dict containing all of the
        hosts on which the process is assigned. The key to the dict is the
        fully qualified domain name of the host on which the process is
        assigned. The value is a dict containing the environment configured for
        the process on that host, the schedule for when the process should run
        if there is a schedule, whether the proggram should be a daemon, and
        whether or not the process is disabled on that host. No checks are
        performed to see if the process name is valid. In both the case where
        the process name is not valid and the case where the process is not
        active on any hosts this will return an empty dict.
    """
    s = __get_session()

    details = dict()
    query = cassandra.query.SimpleStatement("""
        SELECT
            fqdn,
            environment,
            disabled
        FROM dart.assignment
        WHERE process = %s
    """)
    rows = s.execute(query, (process,))
    for row in rows:
        details[row["fqdn"]] = dict(
            fqdn=row["fqdn"],
            environment=row["environment"],
            disabled=row["disabled"],
            configuration=None,
            schedule=None,
            daemon=False
        )

    # get any configurations for these processes. since a process can have
    # multiple environments we try to line up the configuration with the
    # correct environment for the host in question
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            environment,
            configuration
        FROM dart.configured
        WHERE process = %s
          AND environment = %s
    """)
    for fqdn in details:
        futures.append(s.execute_async(future_query, [process, details[fqdn]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            for fqdn, value in details.items():
                if (value["environment"] == row["environment"]):
                    details[fqdn]["configuration"] = row["configuration"]

    # get any schedules for these processes. since a process can have multiple
    # environments we try to line up the schedule with the correct environment
    # for the host in question.
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            environment,
            schedule
        FROM dart.schedule
        WHERE process = %s
          AND environment = %s
    """)
    for fqdn in details:
        futures.append(s.execute_async(future_query, [process, details[fqdn]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            for fqdn, value in details.items():
                if (value["environment"] == row["environment"]):
                    details[fqdn]["schedule"] = row["schedule"]
                    try:
                        import datetime
                        from crontab import CronTab
                        crontab = CronTab(row["schedule"])
                        now = datetime.datetime.utcnow()
                        details[fqdn]["starts"] = now + datetime.timedelta(seconds=(int(crontab.next(default_utc=False) + 1)))
                    except ValueError as e:
                        pass

    # get the state monitoring configuration for this process on this host
    # so that we can alert to the fact that this process might need to be
    # running when it isn't
    futures = []
    future_query = cassandra.query.SimpleStatement("""
        SELECT
            process,
            environment
        FROM dart.process_daemon_monitor
        WHERE process = %s
          AND environment = %s
    """)
    for fqdn in details:
        futures.append(s.execute_async(future_query, [process, details[fqdn]["environment"]]))

    for future in futures:
        rows = future.result()
        for row in rows:
            for fqdn, value in details.items():
                if (value["environment"] == row["environment"]):
                    details[fqdn]["daemon"] = True

    return details


def assign(process, environment, fqdn):
    """
        Given a process name, an environment, and a fully qualified domain name
        this will assign the process environment to the host with that fully
        qualified domain name. If the process name is invalid or the
        environment name does not exist for the given process then this will
        raise a DartProcessEnvironmentDoesNotExistException exception. If the
        fully qualified domain name is not the name of a valid host then this
        will raise the DartHostDoesNotExistException exception. If the process
        environment is already assigned to the host then this is a noop.
    """
    if (not is_valid_host(fqdn)):
        raise exceptions.DartHostDoesNotExistException("{} does not exist".format(fqdn))

    if (not is_valid_process(process, environment)):
        raise exceptions.DartProcessEnvironmentDoesNotExistException("{} {} does not exist".format(process, environment))

    s = __get_session()
    query = cassandra.query.SimpleStatement("""
        INSERT INTO dart.assignment (fqdn, process, environment)
        VALUES (%s, %s, %s)
    """)
    s.execute(query, (fqdn, process, environment))


def unassign(process, fqdn):
    """
        Given a process name and a fully qualified domain name this will
        unassign the process from the host with that fully qualified domain
        name. If the process name is invalid then this will raise the
        DartProcessDoesNotExistException exception. If the fully qualified
        domain name is not the name of a valid host then this will raise the
        DartHostDoesNotExistException exception. If the process is not assigned
        to the host with the given fully qualified domain name then this is a
        noop.
    """
    if (not is_valid_host(fqdn)):
        raise exceptions.DartHostDoesNotExistException("{} does not exist".format(fqdn))

    if (not is_valid_process(process)):
        raise exceptions.DartProcessDoesNotExistException("{} does not exist".format(process))

    s = __get_session()
    query = cassandra.query.SimpleStatement("""
        DELETE FROM dart.assignment
        WHERE fqdn = %s
          AND process = %s
    """)
    s.execute(query, (fqdn, process))


def enable(process, fqdn):
    """
        Given a process name and a fully qualified domain name this will enable
        a process on the host with that fully qualified domain name. If the
        process name is not valid then this will raise the
        DartProcessDoesNotExistException exception. If the fully qualified
        domain name is not the name of a valid host then this will raise the
        DartHostDoesNotExistException exception. If the process is not assigned
        to the host with the given fully qualified domain name then this will
        raise the DartProcessNotAssignedException exception. If the process is
        already enabled then this is a noop.

        It is important to note that "enabling" a process only impacts the
        following things:

        * enables log, state, and daemon monitoring by dart
        * enables starting the process on its schedule

        That is to say that if a process is "enabled" then it will be started
        on its schedule and if it throws events that are monitored then the
        log, state, or daemon monitoring system will raise those into the
        event management system.

        For more information see the disable function.
    """
    if (not is_valid_host(fqdn)):
        raise exceptions.DartHostDoesNotExistException("{} does not exist".format(fqdn))

    if (not is_valid_process(process)):
        raise exceptions.DartProcessDoesNotExistException("{} does not exist".format(process))

    if (not is_process_assigned_to_host(fqdn, process)):
        raise exceptions.DartProcessNotAssignedException("{} is not assigned to {}".format(process, fqdn))

    s = __get_session()
    query = cassandra.query.SimpleStatement("""
        UPDATE dart.assignment
        SET disabled = FALSE
        WHERE fqdn = %s
          AND process = %s
    """)
    s.execute(query, (fqdn, process))


def disable(process, fqdn):
    """
        Given a process name and a fully qualified domain name this will
        disable a process on the host with the given fully qualified domain
        name. If the process name is not valid then this will raise the
        DartProcessDoesNotExistException exception. If the fully qualified
        domain name is not the name of a valid host then this will raise the
        DartHostDoesNotExistException exception. If the process is not assigned
        to the host with the given fully qualified domain name then this will
        raise the DartProcessNotAssignedException exception. If the process is
        already disabled then this is a noop.

        It is important to note that "disabling" a process only impacts the
        following things:

        * disables log, state, and daemon monitoring by dart but does not clear
          any existing alerts in the event management system
        * disables starting the process on its schedule

        That is to say that if a process is "disabled" then it will NOT be
        started on its schedule. It can still be started manually if it is an
        actively configured process. Further, if the process does run and it
        throws events that are monitored then the log, state, or daemon
        monitoring system will raise those into the event management system.

        For more information see the enable function.
    """
    if (not is_valid_host(fqdn)):
        raise exceptions.DartHostDoesNotExistException("{} does not exist".format(fqdn))

    if (not is_valid_process(process)):
        raise exceptions.DartProcessDoesNotExistException("{} does not exist".format(process))

    if (not is_process_assigned_to_host(fqdn, process)):
        raise exceptions.DartProcessNotAssignedException("{} is not assigned to {}".format(process, fqdn))

    s = __get_session()
    query = cassandra.query.SimpleStatement("""
        UPDATE dart.assignment
        SET disabled = TRUE
        WHERE fqdn = %s
          AND process = %s
    """)
    s.execute(query, (fqdn, process))


def delete_host(fqdn):
    """
        Given a fully qualified domain name this will delete all records for
        the host with the given fully qualified domain name. No checks are
        performed to see if the fully qualified domain name is the name of a
        valid host. This will simply delete any record that matches the given
        fully qualified domain name.
    """
    s = __get_session()

    # we don't check to see if this is a valid host before trying to delete it.
    # we just want to clear it out of cassandra. this is because we can't put
    # cassandra queries into transactions so it is possible that we have junk
    # about a host in there somewhere.
    for table in ["probe", "probe_partition", "probe_network", "probe_monitor",
                  "assignment", "configured_active", "configured_pending", "host_tag"]:
        query = cassandra.query.SimpleStatement("""
            DELETE FROM dart.{}
            WHERE fqdn = %s
        """.format(table))
        s.execute(query, (fqdn,))


def delete_process(process, environment=None):
    """
        Given a process name this will delete all records for that process. If
        the optional environment name is provided then only records for the
        process in that environment will be deleted. No checks are performed to
        see if the process name or environment name are valid. This will simply
        delete any record that matches the process name and optionally the
        environment name.
    """
    s = __get_session()

    if (environment is not None):
        # don't validate that the process exists first. we want to clear it
        # out of everything regardless. this is because we can't put
        # cassandra queries into a transaction.
        for table in ["configured", "schedule",
                      "process_daemon_monitor", "process_state_monitor"]:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.{}
                WHERE process = %s
                  AND environment = %s
            """.format(table))
            s.execute(query, (process, environment))

        # special cases below:
        # cassandra won't let us delete without the whole primary key and the
        # "process" column is not the only part of the primary key column so we
        # need to query the database for what to delete. very frustrating. we
        # also need to use the "ALLOW FILTERING" option because of the
        # particular way that this table was built.

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                process,
                environment
            FROM dart.assignment
            WHERE process = %s
              AND environment = %s
            ALLOW FILTERING
        """)
        rows = s.execute(query, (process, environment))
        for row in rows:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.assignment
                WHERE fqdn = %s
                  AND process = %s
                  AND environment = %s
            """)
            s.execute(query, (row["fqdn"], row["process"], row["environment"]))

        query = cassandra.query.SimpleStatement("""
            SELECT process, environment, stream
            FROM dart.process_log_monitor
            WHERE process = %s
              AND environment = %s
            ALLOW FILTERING
        """)
        rows = s.execute(query, (process, environment))
        for row in rows:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.process_log_monitor
                WHERE process = %s
                  AND environment = %s
                  AND stream = %s
            """)
            s.execute(query, (row["process"], row["environment"], row["stream"]))
    else:
        # don't validate that the process exists first. we want to clear it
        # out of everything regardless. this is because we can't put
        # cassandra queries into a transaction.
        for table in ["configured", "schedule",
                      "process_daemon_monitor", "process_state_monitor"]:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.{}
                WHERE process = %s
            """.format(table))
            s.execute(query, (process,))

        # special cases below:
        # cassandra won't let us delete without the whole primary key and the
        # "process" column is not the only part of the primary key column so we
        # need to query the database for what to delete. very frustrating. we
        # also need to use the "ALLOW FILTERING" option because of the
        # particular way that this table was built.

        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                process,
                environment
            FROM dart.assignment
            WHERE process = %s
            ALLOW FILTERING
        """)
        rows = s.execute(query, (process,))
        for row in rows:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.assignment
                WHERE fqdn = %s
                  AND process = %s
                  AND environment = %s
            """)
            s.execute(query, (row["fqdn"], row["process"], row["environment"]))

        query = cassandra.query.SimpleStatement("""
            SELECT process, environment, stream
            FROM dart.process_log_monitor
            WHERE process = %s
            ALLOW FILTERING
        """)
        rows = s.execute(query, (process,))
        for row in rows:
            query = cassandra.query.SimpleStatement("""
                DELETE FROM dart.process_log_monitor
                WHERE process = %s
                  AND environment = %s
                  AND stream = %s
            """)
            s.execute(query, (row["process"], row["environment"], row["stream"]))
