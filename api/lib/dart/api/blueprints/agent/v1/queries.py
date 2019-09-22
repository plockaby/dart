from ....app import db_client


def get_assigned_processes(fqdn):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.name, p.environment, p.type, p.configuration, p.schedule, a.disabled
                FROM dart.assignment a
                INNER JOIN dart.host h    ON a.fqdn = h.fqdn
                INNER JOIN dart.process p ON a.process_name = p.name AND a.process_environment = p.environment
                WHERE h.fqdn = %s
                ORDER BY p.name, p.environment
            """, (fqdn,))
            for row in cur:
                # fill in some monitoring information
                row["monitors"] = {}

                # state monitor information
                with conn.cursor() as subcur:
                    subcur.execute("""
                        SELECT contact, severity
                        FROM dart.process_state_monitor
                        WHERE process_name = %s
                          AND process_environment = %s
                    """, (row["name"], row["environment"]))
                    subrow = subcur.fetchone()
                    try:
                        row["monitors"]["state"] = subrow
                    except (json.JSONDecodeError, TypeError):
                        row["monitors"]["state"] = None

                # daemon monitor information
                with conn.cursor() as subcur:
                    subcur = conn.cursor()
                    subcur.execute("""
                        SELECT contact, severity
                        FROM dart.process_daemon_monitor
                        WHERE process_name = %s
                          AND process_environment = %s
                    """, (row["name"], row["environment"]))
                    subrow = subcur.fetchone()
                    try:
                        row["monitors"]["daemon"] = subrow
                    except (json.JSONDecodeError, TypeError):
                        row["monitors"]["daemon"] = None

                # keepalive monitor information
                with conn.cursor() as subcur:
                    subcur = conn.cursor()
                    subcur.execute("""
                        SELECT timeout, contact, severity
                        FROM dart.process_keepalive_monitor
                        WHERE process_name = %s
                          AND process_environment = %s
                    """, (row["name"], row["environment"]))
                    subrow = subcur.fetchone()
                    try:
                        row["monitors"]["keepalive"] = subrow
                    except (json.JSONDecodeError, TypeError):
                        row["monitors"]["keepalive"] = None

                # log monitor information
                with conn.cursor() as subcur:
                    row["monitors"]["log"] = {"stdout": [], "stderr": []}
                    subcur = conn.cursor()
                    subcur.execute("""
                        SELECT stream, regex, stop, name, contact, severity
                        FROM dart.process_log_monitor
                        WHERE process_name = %s
                          AND process_environment = %s
                        ORDER BY stream, sort_order
                    """, (row["name"], row["environment"]))
                    for subrow in subcur:
                        stream = subrow.pop("stream")
                        try:
                            row["monitors"]["log"][stream].append(subrow)
                        except (json.JSONDecodeError, TypeError):
                            pass
    
                # return the rows as we get them
                yield row


def insert_fqdn(fqdn):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.host (fqdn)
                VALUES (%s)
                ON CONFLICT DO NOTHING
            """, (fqdn,))


def delete_active(fqdn, active):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.active_process
                WHERE fqdn = %s
                  AND name != ALL(%s)
            """, (fqdn, active))


def insert_active(fqdn, name, state, started, stopped, stdout, stderr, pid, exit_status, description, error):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.active_process (fqdn, name, state, started, stopped, stdout_logfile, stderr_logfile, pid, exit_status, description, error, polled)
                VALUES (%s, %s, %s, to_timestamp(%s), to_timestamp(%s), %s, %s, %s, %s, %s, %s, transaction_timestamp())
                ON CONFLICT (fqdn, name) DO UPDATE
                SET state = excluded.state,
                    started = excluded.started,
                    stopped = excluded.stopped,
                    stdout_logfile = excluded.stdout_logfile,
                    stderr_logfile = excluded.stderr_logfile,
                    pid = excluded.pid,
                    exit_status = excluded.exit_status,
                    description = excluded.description,
                    error = excluded.error,
                    polled = excluded.polled
            """, (fqdn, name, state, started, stopped, stdout, stderr, pid, exit_status, description, error))


def delete_pending(fqdn, pending):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM dart.pending_process
                WHERE fqdn = %s
                  AND name != ALL(%s)
            """, (fqdn, pending))


def insert_pending(fqdn, process, state):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.pending_process (fqdn, name, state, polled)
                VALUES (%s, %s, %s, transaction_timestamp())
                ON CONFLICT (fqdn, name) DO UPDATE
                SET state = excluded.state,
                    polled = excluded.polled
            """, (fqdn, process, state))


def insert_host(fqdn, booted, kernel):
    with db_client.conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dart.host (fqdn, booted, kernel, polled)
                VALUES (%s, to_timestamp(%s), %s, transaction_timestamp())
                ON CONFLICT (fqdn) DO UPDATE
                SET booted = excluded.booted,
                    kernel = excluded.kernel,
                    polled = excluded.polled
            """, (fqdn, booted, kernel))
