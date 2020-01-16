GRANT SELECT ON TABLE dart.host TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.host TO dart;

GRANT SELECT ON TABLE dart.process TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process TO dart;

GRANT SELECT ON TABLE dart.assignment TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.assignment TO dart;

GRANT SELECT ON TABLE dart.active_process TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.active_process TO dart;

GRANT SELECT ON TABLE dart.pending_process TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.pending_process TO dart;

GRANT SELECT ON TABLE dart.process_state_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_state_monitor TO dart;

GRANT SELECT ON TABLE dart.process_daemon_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_daemon_monitor TO dart;

GRANT SELECT ON TABLE dart.process_heartbeat_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_heartbeat_monitor TO dart;

GRANT SELECT ON TABLE dart.process_log_monitor TO PUBLIC;
GRANT INSERT,DELETE,UPDATE ON TABLE dart.process_log_monitor TO dart;
