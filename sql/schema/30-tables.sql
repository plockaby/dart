CREATE TABLE dart.host (
    fqdn TEXT NOT NULL,
    booted TIMESTAMP WITH TIME ZONE,
    kernel TEXT,
    polled TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE dart.host IS 'all hosts that are managed by dart, automatically populated, manually removed';
COMMENT ON COLUMN dart.host.booted IS 'when the host was last rebooted';
COMMENT ON COLUMN dart.host.kernel IS 'the kernel that the host is running';
ALTER TABLE dart.host ADD PRIMARY KEY (fqdn);

-------------------------------------------------------------------------------

CREATE TABLE dart.process (
    name TEXT NOT NULL,
    environment TEXT NOT NULL,
    type TEXT NOT NULL,
    configuration TEXT NOT NULL,
    schedule TEXT,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT statement_timestamp() NOT NULL,
    modified_by TEXT DEFAULT standard.get_user_id() NOT NULL
);

COMMENT ON TABLE dart.process IS 'process configurations for supervisord, manually populated, manually removed';
ALTER TABLE dart.process ADD PRIMARY KEY (name, environment);
ALTER TABLE dart.process ADD CHECK (type = 'program' OR type = 'eventlistener');

-------------------------------------------------------------------------------

CREATE TABLE dart.assignment (
    fqdn TEXT NOT NULL,
    process_name TEXT NOT NULL,
    process_environment TEXT NOT NULL,
    disabled boolean DEFAULT false NOT NULL,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT statement_timestamp() NOT NULL,
    modified_by TEXT DEFAULT standard.get_user_id() NOT NULL
);

COMMENT ON TABLE dart.assignment IS 'processes assigned to hosts, populated manually by users, manually removed';
ALTER TABLE dart.assignment ADD PRIMARY KEY (fqdn, process_name);
ALTER TABLE dart.assignment ADD FOREIGN KEY (fqdn) REFERENCES dart.host (fqdn) ON DELETE RESTRICT;
ALTER TABLE dart.assignment ADD FOREIGN KEY (process_name, process_environment) REFERENCES dart.process (name, environment) ON DELETE RESTRICT;

-------------------------------------------------------------------------------

CREATE TABLE dart.active_process (
    fqdn TEXT NOT NULL,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    started TIMESTAMP WITH TIME ZONE NOT NULL,
    stopped TIMESTAMP WITH TIME ZONE NOT NULL,
    stdout_logfile TEXT,
    stderr_logfile TEXT,
    pid bigint NOT NULL,
    exit_status INTEGER,
    description TEXT,
    error TEXT,
    polled TIMESTAMP WITH TIME ZONE NOT NULL
);

COMMENT ON TABLE dart.active_process IS 'processes currently active on hosts, automatically populated, automatically removed';
COMMENT ON COLUMN dart.active_process.state IS 'corresponds with supervisord "statename"';
COMMENT ON COLUMN dart.active_process.exit_status IS 'corresponds with supervisord "exitstatus"';
COMMENT ON COLUMN dart.active_process.error IS 'corresponds with supervisord "spawnerr"';
COMMENT ON COLUMN dart.active_process.polled IS 'when we last received an update for this process';
ALTER TABLE dart.active_process ADD PRIMARY KEY (fqdn, name);
ALTER TABLE dart.active_process ADD FOREIGN KEY (fqdn) REFERENCES dart.host (fqdn) ON DELETE CASCADE;

-------------------------------------------------------------------------------

CREATE TABLE dart.pending_process (
    fqdn TEXT NOT NULL,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    polled TIMESTAMP WITH TIME ZONE NOT NULL
);

COMMENT ON TABLE dart.pending_process IS 'processes currently pending on hosts, automatically populated, automatically removed';
ALTER TABLE dart.pending_process ADD PRIMARY KEY (fqdn, name);
ALTER TABLE dart.pending_process ADD FOREIGN KEY (fqdn) REFERENCES dart.host(fqdn) ON DELETE CASCADE;
ALTER TABLE dart.pending_process ADD CHECK (state = 'changed' OR state = 'added' OR state = 'removed');

-------------------------------------------------------------------------------

CREATE TABLE dart.process_state_monitor (
    process_name TEXT NOT NULL,
    process_environment TEXT NOT NULL,
    ci TEXT NOT NULL,
    severity TEXT NOT NULL,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT statement_timestamp() NOT NULL,
    modified_by TEXT DEFAULT standard.get_user_id() NOT NULL
);

COMMENT ON TABLE dart.process_state_monitor IS 'state monitoring configurations, manually populated, automatically removed';
ALTER TABLE dart.process_state_monitor ADD PRIMARY KEY (process_name, process_environment);
ALTER TABLE dart.process_state_monitor ADD FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
ALTER TABLE dart.process_state_monitor ADD CHECK (severity IN ('OK', '1', '2', '3', '4', '5'));

-------------------------------------------------------------------------------

CREATE TABLE dart.process_daemon_monitor (
    process_name TEXT NOT NULL,
    process_environment TEXT NOT NULL,
    ci TEXT NOT NULL,
    severity TEXT NOT NULL,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT statement_timestamp() NOT NULL,
    modified_by TEXT DEFAULT standard.get_user_id() NOT NULL
);

COMMENT ON TABLE dart.process_daemon_monitor IS 'daemon monitoring configurations, manually populated, automatically removed';
ALTER TABLE dart.process_daemon_monitor ADD PRIMARY KEY (process_name, process_environment);
ALTER TABLE dart.process_daemon_monitor ADD FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
ALTER TABLE dart.process_daemon_monitor ADD CHECK (severity IN ('OK', '1', '2', '3', '4', '5'));

-------------------------------------------------------------------------------

CREATE TABLE dart.process_heartbeat_monitor (
    process_name TEXT NOT NULL,
    process_environment TEXT NOT NULL,
    timeout INTEGER NOT NULL,
    ci TEXT NOT NULL,
    severity TEXT NOT NULL,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT statement_timestamp() NOT NULL,
    modified_by TEXT DEFAULT standard.get_user_id() NOT NULL
);

COMMENT ON TABLE dart.process_heartbeat_monitor IS 'heartbeat monitoring configurations, manually populated, automatically removed';
ALTER TABLE dart.process_heartbeat_monitor ADD PRIMARY KEY (process_name, process_environment);
ALTER TABLE dart.process_heartbeat_monitor ADD FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
ALTER TABLE dart.process_heartbeat_monitor ADD CHECK (severity IN ('OK', '1', '2', '3', '4', '5'));

-------------------------------------------------------------------------------

CREATE TABLE dart.process_log_monitor (
    process_name TEXT NOT NULL,
    process_environment TEXT NOT NULL,
    stream TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    regex TEXT NOT NULL,
    stop BOOLEAN DEFAULT FALSE,
    name TEXT,
    ci TEXT,
    severity TEXT,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT statement_timestamp() NOT NULL,
    modified_by TEXT DEFAULT standard.get_user_id() NOT NULL
);

COMMENT ON TABLE dart.process_log_monitor IS 'log monitoring configurations, manually populated, automatically removed';
COMMENT ON COLUMN dart.process_log_monitor.stream IS 'the output stream to monitor';
COMMENT ON COLUMN dart.process_log_monitor.sort_order IS 'the order in which to apply monitoring configurations';
COMMENT ON COLUMN dart.process_log_monitor.regex IS 'the regular expression to apply to the log line';
COMMENT ON COLUMN dart.process_log_monitor.stop IS 'if true then if this matches no more log monitors will be applied';
COMMENT ON COLUMN dart.process_log_monitor.name IS 'a name to give to the log monitor for the event monitoring';
ALTER TABLE dart.process_log_monitor ADD PRIMARY KEY (process_name, process_environment, stream, sort_order);
ALTER TABLE dart.process_log_monitor ADD FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
ALTER TABLE dart.process_log_monitor ADD CHECK (sort_order >= 0);
ALTER TABLE dart.process_log_monitor ADD CHECK (stream IN ('stdout', 'stderr'));
ALTER TABLE dart.process_log_monitor ADD CHECK (severity IN ('OK', '1', '2', '3', '4', '5'));
