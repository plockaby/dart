CREATE TRIGGER t11_anchored_column_fqdn BEFORE UPDATE ON dart.host FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('fqdn');
CREATE TRIGGER t50_distinct_update BEFORE UPDATE ON dart.host FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update();

CREATE TRIGGER t11_anchored_column_environment BEFORE UPDATE ON dart.process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('environment');
CREATE TRIGGER t11_anchored_column_name BEFORE UPDATE ON dart.process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('name');

CREATE TRIGGER t11_anchored_column_fqdn BEFORE UPDATE ON dart.active_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('fqdn');
CREATE TRIGGER t11_anchored_column_name BEFORE UPDATE ON dart.active_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('name');
CREATE TRIGGER t50_distinct_update BEFORE UPDATE ON dart.active_process FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update();

CREATE TRIGGER t11_anchored_column_fqdn BEFORE UPDATE ON dart.pending_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('fqdn');
CREATE TRIGGER t11_anchored_column_name BEFORE UPDATE ON dart.pending_process FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column('name');
CREATE TRIGGER t50_distinct_update BEFORE UPDATE ON dart.pending_process FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update();
