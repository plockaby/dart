from ....app import db_client
from datetime import datetime, timedelta
from crontab import CronTab
import json


def is_valid_host(fqdn):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM dart.host
                WHERE fqdn = %s
            """, (fqdn,))
            row = cur.fetchone()
            return (row["total"] > 0)


def is_valid_process(name, environment=None):
    if (not environment):
        with db_client.conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) AS total
                    FROM dart.process
                    WHERE name = %s
                """, (name,))
                row = cur.fetchone()
                return (row["total"] > 0)

    else:
        with db_client.conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) AS total
                    FROM dart.process
                    WHERE name = %s
                      AND environment = %s
                """, (name, environment))
                row = cur.fetchone()
                return (row["total"] > 0)


def select_hosts():
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
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    h.fqdn,
                    to_char(h.polled, 'YYYY-MM-DD HH24:MI:SS') AS polled,
                    (SELECT COUNT(*) FROM dart.active_process WHERE fqdn = h.fqdn) AS total,
                    (SELECT COUNT(*) FROM dart.active_process WHERE fqdn = h.fqdn AND state = 'RUNNING') AS running,
                    (SELECT COUNT(*) FROM dart.active_process WHERE fqdn = h.fqdn AND state IN ('STOPPED', 'STOPPING', 'EXITED')) AS stopped,
                    (SELECT COUNT(*) FROM dart.active_process WHERE fqdn = h.fqdn AND state IN ('BACKOFF', 'FATAL', 'UNKNOWN')) AS failed,
                    (SELECT COUNT(*) FROM dart.pending_process WHERE fqdn = h.fqdn) AS pending,
                    (SELECT COUNT(*) FROM dart.assignment WHERE fqdn = h.fqdn) AS assigned,
                    (SELECT COUNT(*) FROM dart.assignment WHERE fqdn = h.fqdn AND disabled IS TRUE) AS disabled
                FROM dart.host h
                ORDER BY h.fqdn
            """)
            yield from cur


def select_host(fqdn):
    result = None

    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    fqdn,
                    to_char(booted, 'YYYY-MM-DD HH24:MI:SS') AS booted,
                    kernel,
                    to_char(polled, 'YYYY-MM-DD HH24:MI:SS') AS polled
                FROM dart.host
                WHERE fqdn = %s
            """, (fqdn,))
            result = cur.fetchone()

        if (result is None):
            return

        result["assignments"] = []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.process_name AS name,
                    a.process_environment AS environment,
                    p.type,
                    p.schedule,
                    a.disabled,
                    (pdm.ci IS NOT NULL) AS daemon
                FROM dart.assignment a
                INNER JOIN dart.process p                       ON p.name = a.process_name AND p.environment = a.process_environment
                LEFT OUTER JOIN dart.process_daemon_monitor pdm ON pdm.process_name = a.process_name AND pdm.process_environment = a.process_environment
                WHERE a.fqdn = %s
                ORDER BY a.process_name, a.process_environment
            """, (fqdn,))
            for row in cur:
                if (row["schedule"] is not None):
                    try:
                        crontab = CronTab(row["schedule"])
                        now = datetime.now()
                        row["starts"] = (now + timedelta(seconds=(int(crontab.next(default_utc=True)) + 1))).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        row["starts"] = None
                result["assignments"].append(row)

        result["active"] = []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ap.name,
                    p.environment,
                    ap.state,
                    ap.description,
                    ap.error,
                    a.disabled,
                    p.schedule,
                    (pdm.ci IS NOT NULL) AS daemon
                FROM dart.active_process ap
                LEFT OUTER JOIN dart.assignment a               ON a.process_name = ap.name AND a.fqdn = ap.fqdn
                LEFT OUTER JOIN dart.process_daemon_monitor pdm ON pdm.process_name = a.process_name AND pdm.process_environment = a.process_environment
                LEFT OUTER JOIN dart.process p                  ON p.name = a.process_name AND p.environment = a.process_environment
                WHERE ap.fqdn = %s
                ORDER BY ap.name
            """, (fqdn,))
            for row in cur:
                if (row["schedule"] is not None):
                    try:
                        crontab = CronTab(row["schedule"])
                        now = datetime.now()
                        row["starts"] = (now + timedelta(seconds=(int(crontab.next(default_utc=True)) + 1))).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        row["starts"] = None
                result["active"].append(row)

        result["pending"] = []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.name,
                    p.state,
                    a.disabled
                FROM dart.pending_process p
                LEFT OUTER JOIN dart.assignment a ON a.process_name = p.name AND a.fqdn = p.fqdn
                WHERE p.fqdn = %s
                ORDER BY p.name
            """, (fqdn,))
            for row in cur:
                result["pending"].append(row)

    return result


def delete_host(fqdn):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.host
                WHERE fqdn = %s
            """, (fqdn,))


def select_processes():
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
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.name,
                    (SELECT COUNT(*) FROM dart.active_process WHERE name = p.name) AS active,
                    (SELECT COUNT(*) FROM dart.active_process WHERE name = p.name AND state IN ('BACKOFF', 'FATAL', 'UNKNOWN')) AS failed,
                    (SELECT COUNT(*) FROM dart.pending_process WHERE name = p.name) AS pending,
                    (SELECT COUNT(*) FROM dart.assignment WHERE process_name = p.name) AS assigned,
                    (SELECT COUNT(*) FROM dart.assignment WHERE process_name = p.name AND disabled IS TRUE) AS disabled,
                    (SELECT COUNT(*) FROM dart.process WHERE name = p.name) AS configured,
                    array_remove((SELECT array_agg(DISTINCT fqdn) FROM dart.active_process WHERE name = p.name), NULL) AS active_hosts,
                    array_remove((SELECT array_agg(DISTINCT fqdn) FROM dart.pending_process WHERE name = p.name), NULL) AS pending_hosts,
                    array_remove((SELECT array_agg(DISTINCT fqdn) FROM dart.assignment WHERE process_name = p.name), NULL) AS assigned_hosts,
                    array_remove((SELECT array_agg(DISTINCT fqdn) FROM dart.assignment WHERE process_name = p.name AND disabled IS TRUE), NULL) AS disabled_hosts
                FROM (
                    SELECT name FROM dart.process
                    UNION
                    SELECT name FROM dart.active_process
                    UNION
                    SELECT name FROM dart.pending_process
                ) p
                GROUP BY p.name
                ORDER BY p.name
            """)
            for row in cur:
                # if no hosts are returned it will be None and we need them to be lists
                if (row["active_hosts"] is None):
                    row["active_hosts"] = []
                if (row["pending_hosts"] is None):
                    row["pending_hosts"] = []
                if (row["assigned_hosts"] is None):
                    row["assigned_hosts"] = []
                if (row["disabled_hosts"] is None):
                    row["disabled_hosts"] = []

                yield row


def select_process(name):
    with db_client.conn() as conn:
        # get the configurations for all environments
        environments = []

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    environment AS name,
                    type,
                    configuration,
                    schedule
                FROM dart.process
                WHERE name = %s
                ORDER BY environment
            """, (name,))
            for row in cur:
                if (row["schedule"] is not None):
                    try:
                        crontab = CronTab(row["schedule"])
                        now = datetime.now()
                        row["starts"] = (now + timedelta(seconds=(int(crontab.next(default_utc=True)) + 1))).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        row["starts"] = None
                environments.append(row)

        # if no configurations then nothing else to do
        if (len(environments) == 0):
            return

        # keep everything in here, this is a dict
        results = {
            "environments": environments,
            "assignments": [],
            "active": [],
            "pending": [],
        }

        # get assignments for this process
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.fqdn,
                    a.process_environment AS environment,
                    p.type,
                    p.schedule,
                    a.disabled
                FROM dart.assignment a
                INNER JOIN dart.process p ON p.name = a.process_name AND p.environment = a.process_environment
                WHERE a.process_name = %s
                ORDER BY a.fqdn, a.process_environment
            """, (name,))
            for row in cur:
                if (row["schedule"] is not None):
                    try:
                        crontab = CronTab(row["schedule"])
                        now = datetime.now()
                        row["starts"] = (now + timedelta(seconds=(int(crontab.next(default_utc=True)) + 1))).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        row["starts"] = None
                results["assignments"].append(row)

        # get active instances of this process
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ap.fqdn,
                    ap.name,
                    p.environment,
                    ap.state,
                    ap.description,
                    ap.error,
                    a.disabled,
                    p.schedule,
                    (pdm.ci IS NOT NULL) AS daemon
                FROM dart.active_process ap
                LEFT OUTER JOIN dart.assignment a               ON a.process_name = ap.name AND a.fqdn = ap.fqdn
                LEFT OUTER JOIN dart.process_daemon_monitor pdm ON pdm.process_name = a.process_name AND pdm.process_environment = a.process_environment
                LEFT OUTER JOIN dart.process p                  ON p.name = a.process_name AND p.environment = a.process_environment
                WHERE ap.name = %s
                ORDER BY ap.fqdn
            """, (name,))
            for row in cur:
                if (row["schedule"] is not None):
                    try:
                        crontab = CronTab(row["schedule"])
                        now = datetime.now()
                        row["starts"] = (now + timedelta(seconds=(int(crontab.next(default_utc=True)) + 1))).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        row["starts"] = None
                results["active"].append(row)

        # get pending instances of this process
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.fqdn,
                    p.state,
                    a.disabled
                FROM dart.pending_process p
                LEFT OUTER JOIN dart.assignment a ON a.process_name = p.name AND a.fqdn = p.fqdn
                WHERE p.name = %s
                ORDER BY p.fqdn
            """, (name,))
            for row in cur:
                results["pending"].append(row)

        # get monitoring configurations for each environment
        results["monitoring"] = {}
        for environment in environments:
            monitors = {}

            # state monitoring
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        ci,
                        severity
                    FROM dart.process_state_monitor
                    WHERE process_name = %s
                      AND process_environment = %s
                """, (name, environment["name"]))
                monitors["state"] = cur.fetchone()

                # decode the ci
                try:
                    monitors["state"]["ci"] = json.loads(monitors["state"]["ci"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    monitors["state"] = None

            # daemon monitoring
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        ci,
                        severity
                    FROM dart.process_daemon_monitor
                    WHERE process_name = %s
                      AND process_environment = %s
                """, (name, environment["name"]))
                monitors["daemon"] = cur.fetchone()

                # decode the ci
                try:
                    monitors["daemon"]["ci"] = json.loads(monitors["daemon"]["ci"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    monitors["daemon"] = None

            # keepalive monitoring
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        ci,
                        severity,
                        timeout
                    FROM dart.process_keepalive_monitor
                    WHERE process_name = %s
                      AND process_environment = %s
                """, (name, environment["name"]))
                monitors["keepalive"] = cur.fetchone()

                # decode the ci
                try:
                    monitors["keepalive"]["ci"] = json.loads(monitors["keepalive"]["ci"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    monitors["keepalive"] = None

            # log monitoring
            monitors["log"] = {"stdout": [], "stderr": []}
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        sort_order AS id,
                        stream,
                        regex,
                        name,
                        ci,
                        severity,
                        stop
                    FROM dart.process_log_monitor
                    WHERE process_name = %s
                      AND process_environment = %s
                    ORDER BY stream, sort_order
                """, (name, environment["name"]))
                for row in cur:
                    try:
                        # if the ci isn't valid then don't append. it's
                        # probably# completely invalid if the ci doesn't decode
                        row["ci"] = json.loads(row["ci"])
                        monitors["log"][row["stream"]].append(row)
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass

                    monitors["log"][row["stream"]].append(row)

            results["monitoring"][environment["name"]] = monitors

    return results


def delete_process(name, environment=None):
    if (environment is None):
        with db_client.conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM dart.process
                    WHERE name = %s
                """, (name,))

    else:
        with db_client.conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM dart.process
                    WHERE name = %s AND environment = %s
                """, (name, environment))


def insert_host_assignment(fqdn, name, environment):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.assignment (fqdn, process_name, process_environment)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (fqdn, name, environment))


def delete_host_assignment(fqdn, name):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.assignment
                WHERE fqdn = %s
                  AND process_name = %s
            """, (fqdn, name))


def update_process_disabled(fqdn, name, disabled):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE dart.assignment
                SET disabled = %s
                WHERE fqdn = %s
                  AND process_name = %s
            """, (disabled, fqdn, name))


def insert_process(process_name, process_environment, process_type, configuration, schedule):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.process (name, environment, type, configuration, schedule)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name, environment) DO UPDATE
                SET configuration = excluded.configuration,
                    type = excluded.type,
                    schedule = excluded.schedule
            """, (process_name, process_environment, process_type, configuration, schedule))


def insert_process_state_monitor(process_name, process_environment, ci, severity):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.process_state_monitor (process_name, process_environment, ci, severity)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (process_name, process_environment) DO UPDATE
                SET ci = excluded.ci,
                    severity = excluded.severity
            """, (process_name, process_environment, json.dumps(ci), severity))


def delete_process_state_monitor(process_name, process_environment):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.process_state_monitor
                WHERE process_name = %s
                  AND process_environment = %s
            """, (process_name, process_environment))


def insert_process_daemon_monitor(process_name, process_environment, ci, severity):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.process_daemon_monitor (process_name, process_environment, ci, severity)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (process_name, process_environment) DO UPDATE
                SET ci = excluded.ci,
                    severity = excluded.severity
            """, (process_name, process_environment, json.dumps(ci), severity))


def delete_process_daemon_monitor(process_name, process_environment):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.process_daemon_monitor
                WHERE process_name = %s
                  AND process_environment = %s
            """, (process_name, process_environment))


def insert_process_keepalive_monitor(process_name, process_environment, timeout, ci, severity):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.process_keepalive_monitor (process_name, process_environment, timeout, ci, severity)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (process_name, process_environment) DO UPDATE
                SET ci = excluded.ci,
                    severity = excluded.severity
            """, (process_name, process_environment, timeout, json.dumps(ci), severity))


def delete_process_keepalive_monitor(process_name, process_environment):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.process_keepalive_monitor
                WHERE process_name = %s
                  AND process_environment = %s
            """, (process_name, process_environment))


def insert_process_log_monitor(process_name, process_environment, stream, sort_order, regex, stop, name, ci, severity):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.process_log_monitor (process_name, process_environment, stream, sort_order, regex, stop, name, ci, severity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (process_name, process_environment, stream, sort_order) DO UPDATE
                SET regex = excluded.regex,
                    stop = excluded.stop,
                    name = excluded.name,
                    ci = excluded.ci,
                    severity = excluded.severity
            """, (process_name, process_environment, stream, sort_order, regex, stop, name, json.dumps(ci), severity))


def delete_process_log_monitor(process_name, process_environment):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.process_log_monitor
                WHERE process_name = %s
                  AND process_environment = %s
            """, (process_name, process_environment))
