BEGIN;

CREATE ROLE dart;
ALTER ROLE dart WITH LOGIN;

CREATE SCHEMA IF NOT EXISTS dart;
ALTER SCHEMA dart OWNER TO postgres;
GRANT USAGE ON SCHEMA dart TO dart;


CREATE TABLE dart.host (
    fqdn text NOT NULL,
    booted timestamp with time zone,
    kernel text,
    polled timestamp with time zone
);

COMMENT ON TABLE dart.host IS 'all hosts that are managed by dart, automatically populated, manually removed';
COMMENT ON COLUMN dart.host.booted IS 'when the host was last rebooted';
COMMENT ON COLUMN dart.host.kernel IS 'the kernel that the host is running';
ALTER TABLE dart.host OWNER TO postgres;
ALTER TABLE dart.host ADD CONSTRAINT host_pkey PRIMARY KEY (fqdn);
CREATE TRIGGER t11_anchored_column_fqdn BEFORE UPDATE ON dart.host FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('fqdn');
CREATE TRIGGER t30_distinct_update BEFORE UPDATE ON dart.host FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update();
GRANT SELECT ON TABLE dart.host TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.host TO dart;

CREATE TABLE dart.process (
    name text NOT NULL,
    environment text NOT NULL,
    type text NOT NULL,
    configuration text NOT NULL,
    schedule text,
    modified_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    modified_by text DEFAULT standard.get_userid() NOT NULL,
    CONSTRAINT process_type_check CHECK (((type = 'program'::text) OR (type = 'eventlistener'::text)))
);

ALTER TABLE dart.process OWNER TO postgres;
COMMENT ON TABLE dart.process IS 'process configurations for supervisord, manually populated, manually removed';
ALTER TABLE dart.process ADD CONSTRAINT process_pkey PRIMARY KEY (name, environment);
CREATE TRIGGER t11_anchored_column_environment BEFORE UPDATE ON dart.process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('environment');
CREATE TRIGGER t11_anchored_column_name BEFORE UPDATE ON dart.process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('name');
GRANT SELECT ON TABLE dart.process TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process TO dart;

SELECT standard.standardize_table_history_and_trigger('dart', 'process');
ALTER TABLE dart.process_history OWNER TO postgres;

CREATE TABLE dart.assignment (
    fqdn text NOT NULL,
    process_name text NOT NULL,
    process_environment text NOT NULL,
    disabled boolean DEFAULT false NOT NULL,
    modified_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    modified_by text DEFAULT standard.get_userid() NOT NULL
);

ALTER TABLE dart.assignment OWNER TO postgres;
COMMENT ON TABLE dart.assignment IS 'processes assigned to hosts, populated manually by users, manually removed';
ALTER TABLE dart.assignment ADD CONSTRAINT assignment_pkey PRIMARY KEY (fqdn, process_name);
ALTER TABLE dart.assignment ADD CONSTRAINT assignment_fqdn_fkey FOREIGN KEY (fqdn) REFERENCES dart.host(fqdn) ON DELETE RESTRICT;
ALTER TABLE dart.assignment ADD CONSTRAINT assignment_process_name_fkey FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE RESTRICT;
GRANT SELECT ON TABLE dart.assignment TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.assignment TO dart;

SELECT standard.standardize_table_history_and_trigger('dart', 'assignment');
ALTER TABLE dart.assignment_history OWNER TO postgres;

CREATE TABLE dart.active_process (
    fqdn text NOT NULL,
    name text NOT NULL,
    state text NOT NULL,
    started timestamp with time zone,
    stopped timestamp with time zone,
    stdout_logfile text,
    stderr_logfile text,
    pid bigint,
    exit_status integer,
    description text,
    error text,
    polled timestamp with time zone NOT NULL
);

ALTER TABLE dart.active_process OWNER TO postgres;
COMMENT ON TABLE dart.active_process IS 'processes currently active on hosts, automatically populated, automatically removed';
COMMENT ON COLUMN dart.active_process.state IS 'corresponds with supervisord "statename"';
COMMENT ON COLUMN dart.active_process.exit_status IS 'corresponds with supervisord "exitstatus"';
COMMENT ON COLUMN dart.active_process.error IS 'corresponds with supervisord "spawnerr"';
COMMENT ON COLUMN dart.active_process.polled IS 'when we last received an update for this process';
ALTER TABLE dart.active_process ADD CONSTRAINT active_process_pkey PRIMARY KEY (fqdn, name);
ALTER TABLE dart.active_process ADD CONSTRAINT active_process_fqdn_fkey FOREIGN KEY (fqdn) REFERENCES dart.host(fqdn) ON DELETE CASCADE;
CREATE TRIGGER t11_anchored_column_fqdn BEFORE UPDATE ON dart.active_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('fqdn');
CREATE TRIGGER t11_anchored_column_name BEFORE UPDATE ON dart.active_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('name');
CREATE TRIGGER t30_distinct_update BEFORE UPDATE ON dart.active_process FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update();
GRANT SELECT ON TABLE dart.active_process TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.active_process TO dart;

CREATE TABLE dart.pending_process (
    fqdn text NOT NULL,
    name text NOT NULL,
    state text,
    polled timestamp with time zone NOT NULL,
    CONSTRAINT pending_process_state_check CHECK (((state = 'changed'::text) OR (state = 'added'::text) OR (state = 'removed'::text)))
);

ALTER TABLE dart.pending_process OWNER TO postgres;
COMMENT ON TABLE dart.pending_process IS 'processes currently pending on hosts, automatically populated, automatically removed';
ALTER TABLE dart.pending_process ADD CONSTRAINT pending_process_pkey PRIMARY KEY (fqdn, name);
ALTER TABLE dart.pending_process ADD CONSTRAINT pending_process_fqdn_fkey FOREIGN KEY (fqdn) REFERENCES dart.host(fqdn) ON DELETE CASCADE;
CREATE TRIGGER t11_anchored_column_fqdn BEFORE UPDATE ON dart.pending_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('fqdn');
CREATE TRIGGER t11_anchored_column_name BEFORE UPDATE ON dart.pending_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('name');
CREATE TRIGGER t30_distinct_update BEFORE UPDATE ON dart.pending_process FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update();
GRANT SELECT ON TABLE dart.pending_process TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.pending_process TO dart;

CREATE TABLE dart.process_state_monitor (
    process_name text NOT NULL,
    process_environment text NOT NULL,
    ci text NOT NULL,
    severity text NOT NULL,
    modified_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    modified_by text DEFAULT standard.get_userid() NOT NULL,
    CONSTRAINT process_state_monitor_severity_check CHECK (((severity = 'OK'::text) OR (severity = '1'::text) OR (severity = '2'::text) OR (severity = '3'::text) OR (severity = '4'::text) OR (severity = '5'::text)))
);

ALTER TABLE dart.process_state_monitor OWNER TO postgres;
COMMENT ON TABLE dart.process_state_monitor IS 'state monitoring configurations, manually populated, automatically removed';
ALTER TABLE dart.process_state_monitor ADD CONSTRAINT process_state_monitor_pkey PRIMARY KEY (process_name, process_environment);
ALTER TABLE dart.process_state_monitor ADD CONSTRAINT process_state_monitor_process_name_fkey FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
GRANT SELECT ON TABLE dart.process_state_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_state_monitor TO dart;

SELECT standard.standardize_table_history_and_trigger('dart', 'process_state_monitor');
ALTER TABLE dart.process_state_monitor_history OWNER TO postgres;

CREATE TABLE dart.process_daemon_monitor (
    process_name text NOT NULL,
    process_environment text NOT NULL,
    ci text NOT NULL,
    severity text NOT NULL,
    modified_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    modified_by text DEFAULT standard.get_userid() NOT NULL,
    CONSTRAINT process_daemon_monitor_severity_check CHECK (((severity = 'OK'::text) OR (severity = '1'::text) OR (severity = '2'::text) OR (severity = '3'::text) OR (severity = '4'::text) OR (severity = '5'::text)))
);

ALTER TABLE dart.process_daemon_monitor OWNER TO postgres;
COMMENT ON TABLE dart.process_daemon_monitor IS 'daemon monitoring configurations, manually populated, automatically removed';
ALTER TABLE dart.process_daemon_monitor ADD CONSTRAINT process_daemon_monitor_pkey PRIMARY KEY (process_name, process_environment);
ALTER TABLE dart.process_daemon_monitor ADD CONSTRAINT process_daemon_monitor_process_name_fkey FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
GRANT SELECT ON TABLE dart.process_daemon_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_daemon_monitor TO dart;

SELECT standard.standardize_table_history_and_trigger('dart', 'process_daemon_monitor');
ALTER TABLE dart.process_daemon_monitor_history OWNER TO postgres;

CREATE TABLE dart.process_keepalive_monitor (
    process_name text NOT NULL,
    process_environment text NOT NULL,
    timeout integer NOT NULL,
    ci text NOT NULL,
    severity text NOT NULL,
    modified_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    modified_by text DEFAULT standard.get_userid() NOT NULL,
    CONSTRAINT process_keepalive_monitor_severity_check CHECK (((severity = 'OK'::text) OR (severity = '1'::text) OR (severity = '2'::text) OR (severity = '3'::text) OR (severity = '4'::text) OR (severity = '5'::text)))
);

ALTER TABLE dart.process_keepalive_monitor OWNER TO postgres;
COMMENT ON TABLE dart.process_keepalive_monitor IS 'keepalive monitoring configurations, manually populated, automatically removed';
ALTER TABLE dart.process_keepalive_monitor ADD CONSTRAINT process_keepalive_monitor_pkey PRIMARY KEY (process_name, process_environment);
ALTER TABLE dart.process_keepalive_monitor ADD CONSTRAINT process_keepalive_monitor_process_name_fkey FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
GRANT SELECT ON TABLE dart.process_keepalive_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_keepalive_monitor TO dart;

SELECT standard.standardize_table_history_and_trigger('dart', 'process_keepalive_monitor');
ALTER TABLE dart.process_keepalive_monitor_history OWNER TO postgres;

CREATE TABLE dart.process_log_monitor (
    process_name text NOT NULL,
    process_environment text NOT NULL,
    stream text NOT NULL,
    sort_order integer NOT NULL,
    regex text NOT NULL,
    stop boolean DEFAULT false,
    name text,
    ci text,
    severity text,
    modified_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    modified_by text DEFAULT standard.get_userid() NOT NULL,
    CONSTRAINT process_log_monitor_severity_check CHECK (((severity = 'OK'::text) OR (severity = '1'::text) OR (severity = '2'::text) OR (severity = '3'::text) OR (severity = '4'::text) OR (severity = '5'::text))),
    CONSTRAINT process_log_monitor_sort_order_check CHECK ((sort_order >= 0)),
    CONSTRAINT process_log_monitor_stream_check CHECK (((stream = 'stdout'::text) OR (stream = 'stderr'::text)))
);

ALTER TABLE dart.process_log_monitor OWNER TO postgres;
COMMENT ON TABLE dart.process_log_monitor IS 'log monitoring configurations, manually populated, automatically removed';
COMMENT ON COLUMN dart.process_log_monitor.stream IS 'the output stream to monitor';
COMMENT ON COLUMN dart.process_log_monitor.sort_order IS 'the order in which to apply monitoring configurations';
COMMENT ON COLUMN dart.process_log_monitor.regex IS 'the regular expression to apply to the log line';
COMMENT ON COLUMN dart.process_log_monitor.stop IS 'if true then if this matches no more log monitors will be applied';
COMMENT ON COLUMN dart.process_log_monitor.name IS 'a name to give to the log monitor for the event monitoring';
ALTER TABLE dart.process_log_monitor ADD CONSTRAINT process_log_monitor_pkey PRIMARY KEY (process_name, process_environment, stream, sort_order);
ALTER TABLE dart.process_log_monitor ADD CONSTRAINT process_log_monitor_process_name_fkey FOREIGN KEY (process_name, process_environment) REFERENCES dart.process(name, environment) ON DELETE CASCADE;
GRANT SELECT ON TABLE dart.process_log_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_log_monitor TO dart;

SELECT standard.standardize_table_history_and_trigger('dart', 'process_log_monitor');
ALTER TABLE dart.process_log_monitor_history OWNER TO postgres;

COMMIT;
