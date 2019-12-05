BEGIN;

CREATE SCHEMA IF NOT EXISTS standard;
ALTER SCHEMA standard OWNER TO postgres;
GRANT USAGE ON SCHEMA standard TO PUBLIC;


CREATE OR REPLACE FUNCTION standard.anchored_column() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*  Function:     standard.anchored_column(text)
    Description:  Trigger function to be used with the example trigger below to
                  prevent updates on a table from changing a particular column
                  value.
    Affects:      Raises an ERROR an an attempt to modify the specified column,
                  otherwise does not modify data.
    Arguments:    none
    Returns:      new (the updated row)

CREATE TRIGGER t11_anchored_column
    BEFORE UPDATE ON { schema.table}
    FOR EACH ROW
    EXECUTE PROCEDURE standard.anchored_column('name');

COMMENT ON TRIGGER t11_anchored_column ON {schema.table} IS 'reject updates to column {column_name}';
*/
DECLARE
    column_name text := TG_ARGV[0];
    old_value   text;
    new_value   text;
BEGIN
    EXECUTE 'SELECT ('||quote_literal(OLD)||'::'||TG_RELID::regclass||').'||quote_ident(column_name) INTO old_value;
    EXECUTE 'SELECT ('||quote_literal(NEW)||'::'||TG_RELID::regclass||').'||quote_ident(column_name) INTO new_value;

    IF quote_ident(old_value) != quote_ident(new_value) THEN
        RAISE EXCEPTION 'column "%" may not be changed', column_name;
    END IF;
    RETURN NEW;
END;
$$;

ALTER FUNCTION standard.anchored_column() OWNER TO postgres;


CREATE OR REPLACE FUNCTION standard.distinct_update() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*  Function:     standard.distinct_update()
    Description:  Trigger function that will drop an update that does not
                  modify any column on the row. This will prevent the creation
                  of additional history records. See the example trigger below.
    Affects:      makes no changes to data
    Arguments:    none
    Returns:      If there are no changes NULL is returned which ends the
                  processing of the update on that specific row. Otherwise NEW
                  is returned (the updated row).

CREATE TRIGGER t30_distinct_update
    BEFORE UPDATE ON {schema.table}
    FOR EACH ROW
    EXECUTE PROCEDURE standard.distinct_update();

COMMENT ON TRIGGER t30_distinct_update ON {schema.table} IS 'ensure update is distinct';
*/
DECLARE
BEGIN
    -- don't perform update if the row has not been modified
    IF (row(old.*) IS NOT DISTINCT FROM row(new.*)) THEN
        RETURN NULL;
    END IF;

    -- update
    RETURN new;
END;
$$;

ALTER FUNCTION standard.distinct_update() OWNER TO postgres;


CREATE OR REPLACE FUNCTION standard.distinct_update_modified() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*  Function:     standard.distinct_update_modified()
    Description:  Trigger function that will drop an update that does not
                  modify any column on the row. This will prevent the creation
                  of additional history records. See the example trigger below.
    Affects:      makes no changes to data
    Arguments:    none
    Returns:      If there are no changes NULL is returned which ends the
                  processing of the update on that specific row. Otherwise NEW
                  is returned (the updated row).

CREATE TRIGGER t30_distinct_update
    BEFORE UPDATE ON {schema.table}
    FOR EACH ROW
    EXECUTE PROCEDURE standard.distinct_update_modified();

COMMENT ON TRIGGER t30_distinct_update ON {schema.table} IS 'ensure update is distinct';
*/
DECLARE
BEGIN
    -- set old modified* fields to the new values
    old.modified_at := new.modified_at;
    old.modified_by := new.modified_by;

    -- don't perform update if the row has not been modified
    IF (row(old.*) IS NOT DISTINCT FROM row(new.*)) THEN
        RETURN NULL;
    END IF;

    -- update
    RETURN new;
END;
$$;

ALTER FUNCTION standard.distinct_update_modified() OWNER TO postgres;


CREATE OR REPLACE FUNCTION standard.get_userid() RETURNS text
    LANGUAGE plpgsql
AS $$
/*  Function:     standard.get_userid()
    Description:  For retrieving the user identity performing the transaction.
                  Useful as the default value for modified_by or created_by
                  columns. See code below for an example of the usage.
    Affects:      makes no changes to data
    Arguments:    none
    Returns:      varchar with the identity of the current actor

BEGIN;

SET LOCAL local.userid TO {value};

{SQL to run}

COMMIT;
*/
DECLARE
    _userid      varchar;
BEGIN
    _userid := current_setting('local.userid');
    IF _userid IS NULL or _userid ~ E'^\\s*$' THEN
        RETURN CURRENT_USER;
    END IF;
    RETURN _userid;
EXCEPTION
    WHEN OTHERS THEN RETURN CURRENT_USER;
END;
$$;

ALTER FUNCTION standard.get_userid() OWNER TO postgres;


CREATE OR REPLACE FUNCTION standard.history_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
AS $$
/*  Function:     standard.history_trigger()
    Description:  Standard history trigger function which will take the values
                  from an INSERT, UPDATE, DELETE, or TRUNCATE and insert into
                  the appropriate history table. This function requires:

                  1) the base table have the following columns:
                    *) "modified_at  timestamptz"
                    *) "modified_by  text"
                  2) the history table must
                    *) have the same name as the base table
                    *) be in the schema "{base table schema}_history"
                    *) have its first column be modified_action TEXT NOT NULL
                    *) have its second column be txn_timestamp TIMESTAMPTZ
                    *) and then its remaining columns must be the same as the
                       base table in the same order.
                    *) only SELECT should be granted to all users

    Affects:      Inserts row into the history table ({schema}_history.{table})
                  for the table the trigger is placed on.
    Arguments:    none
    Returns:      NEW row on INSERT/UPDATE, OLD row on DELETE, NULL on TRUNCATE

    Note that for a TRUNCATE only a single row is written to the history table.
    That row contains only the command, transaction time, and modified*.
*/
DECLARE
    _parent_table       text;
    _history_table      text;
    _modified_action    text;
    _transaction_time   timestamptz;
BEGIN
    _parent_table := TG_TABLE_SCHEMA||'.'||TG_TABLE_NAME;
    _history_table := TG_TABLE_SCHEMA||'.'||TG_TABLE_NAME||'_history';
    _modified_action := TG_OP;
    _transaction_time := transaction_timestamp();

    IF TG_OP = 'DELETE' THEN
        -- reset these to now instead of what was already in the deleted column
        OLD.modified_at := statement_timestamp();
        OLD.modified_by := standard.get_userid();
        EXECUTE 'INSERT INTO '|| _history_table ||' SELECT $1, $2, $3.*'
            USING _modified_action, _transaction_time, OLD;
        RETURN OLD;

    ELSIF TG_OP = 'TRUNCATE' THEN
        -- everything but these four columns is NULL
        EXECUTE 'INSERT INTO '|| _history_table ||' (modified_action, txn_timestamp, modified_at, modified_by) VALUES ($1, $2, $3, $4)'
            USING _modified_action, _transaction_time, statement_timestamp(), standard.get_userid();
        RETURN NULL;

    ELSE
        EXECUTE 'INSERT INTO '||_history_table||' SELECT $1, $2, $3.*'
            USING _modified_action, _transaction_time, NEW;
        RETURN NEW;
    END IF;
END;
$$;

ALTER FUNCTION standard.history_trigger() OWNER TO postgres;

CREATE OR REPLACE FUNCTION standard.modified() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
/*  Function:     standard.modified()
    Description:  Trigger function for updates and inserts that sets the
                  modified_at column to to statement_timestamp() and the
                  modified_by column to standard.get_userid(). See the example
                  trigger below for use.
    Affects:      Modifies the NEW row as described above.
    Arguments:    none
    Returns:      The NEW row.

CREATE TRIGGER t50_modified
    BEFORE INSERT OR UPDATE ON {schema.table}
    FOR EACH ROW
    EXECUTE PROCEDURE standard.modified();

COMMENT ON TRIGGER t50_modified ON {schema.table} IS 'ensure the modified_* columns are updated';
*/
DECLARE
BEGIN
    new.modified_at := statement_timestamp();
    new.modified_by := standard.get_userid();
    RETURN new;
END;
$$;

ALTER FUNCTION standard.modified() OWNER TO postgres;


CREATE OR REPLACE FUNCTION standard.refresh_materialized_view(_schemaname text, _matviewname text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
AS $$
    DECLARE
        test_ownership BOOLEAN;
        test_concurrent BOOLEAN;
    BEGIN
        -- if we don't own the materialized view then we can't update it
        test_ownership = (
            SELECT true
            FROM pg_catalog.pg_matviews
            WHERE schemaname = _schemaname
              AND matviewname = _matviewname
              AND matviewowner = current_user
        );

        IF (NOT test_ownership) THEN
            RAISE EXCEPTION 'materialized view does not exist or is not updateable';
        END IF;

        -- if the materialized view has a unique key then we can update concurrently
        test_concurrent = (
            SELECT COUNT(*) > 0 FROM (
                SELECT
                    u.usename       AS user_name,
                    ns.nspname      AS schema_name,
                    t.relname       AS table_name,
                    i.relname       AS index_name,
                    idx.indisunique AS is_unique
                FROM pg_index AS idx
                INNER JOIN pg_class i      ON i.oid = idx.indexrelid
                INNER JOIN pg_am am        ON i.relam = am.oid
                INNER JOIN pg_namespace ns ON i.relnamespace = ns.oid
                INNER JOIN pg_user u       ON i.relowner = u.usesysid
                INNER JOIN pg_class t      ON t.oid = idx.indrelid
            ) x
            WHERE x.user_name = current_user
              AND x.schema_name = _schemaname
              AND x.table_name = _matviewname
              AND x.is_unique IS TRUE
        );

        IF (test_concurrent) THEN
            EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || quote_ident(_schemaname) || '.' || quote_ident(_matviewname);
        ELSE
            EXECUTE 'REFRESH MATERIALIZED VIEW ' || quote_ident(_schemaname) || '.' || quote_ident(_matviewname);
        END IF;
    RETURN;
END;
$$;

ALTER FUNCTION standard.refresh_materialized_view(_schemaname text, _matviewname text) OWNER TO postgres;


CREATE OR REPLACE FUNCTION standard.standardize_table_history_and_trigger(v_root_schema text, v_table text) RETURNS void
    LANGUAGE plpgsql
AS $$
/*  Function:     standard.standardize_table_history_and_trigger(schema_name, table_name)
    Description:  Function that will create the necessary history table for a
                  given table.
    Affects:      Creates a new table in "schema_name" called
                  "table_name_history". Creates triggers on provided table.
    Arguments:    text v_root_schema - name of schema the source table lives in
                  text v_table       - name of source table
    Returns:      void

    SELECT standard.standardize_table_history_and_trigger('the_schema', 'the_table');
*/
DECLARE
    _parent_schema      text;
    _parent_table       text;   -- original table name without schema
    _parent_full_table  text;   -- original table name with schema
    _history_schema     text;
    _history_table      text;   -- history table name with schema
    _column             text;
BEGIN
    _parent_schema := quote_ident(v_root_schema);
    _parent_table := quote_ident(v_table);
    _parent_full_table := _parent_schema||'.'||_parent_table;
    _history_schema := _parent_schema;
    _history_table := _history_schema||'.'||_parent_table||'_history';

    -- add history table
    EXECUTE 'CREATE TABLE '||_history_table||' ( modified_action VARCHAR NOT NULL, txn_timestamp TIMESTAMPTZ NOT NULL, LIKE '||_parent_full_table||');';

    -- drop NOT NULL constraints on history table
    FOR _column IN
        SELECT column_name FROM information_schema.columns
            WHERE table_schema = _history_schema
                AND table_name = _parent_table
                AND column_name NOT IN ('modified_action', 'txn_timestamp')
                AND is_nullable = 'NO' LOOP

        EXECUTE 'ALTER TABLE '||_history_table||' ALTER COLUMN '||_column||' DROP NOT NULL';

        IF _column = 'id' THEN
            EXECUTE 'CREATE TRIGGER t10_anchored_column BEFORE UPDATE ON '||_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column(''id'')';
        END IF;
    END LOOP;

    EXECUTE 'GRANT SELECT ON '||_history_table||' to PUBLIC';

    -- create triggers
    EXECUTE 'CREATE TRIGGER t30_distinct_update_modified BEFORE UPDATE ON '||_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update_modified()';
    EXECUTE 'CREATE TRIGGER t50_modified BEFORE INSERT OR UPDATE ON '||_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.modified()';
    EXECUTE 'CREATE TRIGGER t90_history_saver AFTER INSERT OR UPDATE OR DELETE ON '||_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.history_trigger()';
    EXECUTE 'CREATE TRIGGER t90_history_saver_truncate AFTER TRUNCATE ON '||_parent_full_table||' FOR EACH STATEMENT EXECUTE PROCEDURE standard.history_trigger()';
END;
$$;

ALTER FUNCTION standard.standardize_table_history_and_trigger(v_root_schema text, v_table text) OWNER TO postgres;


CREATE OR REPLACE VIEW standard.show_object_ownership AS
 SELECT NULL::name AS schema,
    (n.nspname)::text AS name,
    pg_get_userbyid(n.nspowner) AS owner,
    'schema'::text AS type
   FROM pg_namespace n
  WHERE ((n.nspname !~ '^pg_'::text) AND (n.nspname <> 'information_schema'::name))
UNION ALL
 SELECT n.nspname AS schema,
    ((((p.proname)::text || '('::text) || pg_get_function_arguments(p.oid)) || ')'::text) AS name,
    pg_get_userbyid(p.proowner) AS owner,
        CASE
            WHEN (p.prokind = 'a'::"char") THEN 'aggregate'::text
            WHEN (p.prokind = 'w'::"char") THEN 'window'::text
            WHEN (p.prorettype = ('trigger'::regtype)::oid) THEN 'function'::text
            ELSE 'function'::text
        END AS type
   FROM (pg_proc p
     JOIN pg_namespace n ON ((n.oid = p.pronamespace)))
  WHERE ((n.nspname <> 'pg_catalog'::name) AND (n.nspname <> 'information_schema'::name))
UNION ALL
 SELECT n.nspname AS schema,
    (c.relname)::text AS name,
    pg_get_userbyid(c.relowner) AS owner,
        CASE c.relkind
            WHEN 'r'::"char" THEN 'table'::text
            WHEN 'v'::"char" THEN 'view'::text
            WHEN 'm'::"char" THEN 'materialized view'::text
            WHEN 'i'::"char" THEN 'index'::text
            WHEN 'S'::"char" THEN 'sequence'::text
            WHEN 'f'::"char" THEN 'foreign table'::text
            WHEN 'c'::"char" THEN 'type'::text
            ELSE NULL::text
        END AS type
   FROM (pg_class c
     JOIN pg_namespace n ON ((n.oid = c.relnamespace)))
  WHERE ((n.nspname <> 'pg_catalog'::name) AND (n.nspname <> 'information_schema'::name) AND (n.nspname !~ '^pg_toast'::text))
UNION ALL
 SELECT NULL::name AS schema,
    (s.srvname)::text AS name,
    pg_get_userbyid(s.srvowner) AS owner,
    'foreign server'::text AS type
   FROM pg_foreign_server s
UNION ALL
 SELECT NULL::name AS schema,
    (f.fdwname)::text AS name,
    pg_get_userbyid(f.fdwowner) AS owner,
    'foreign data wrapper'::text AS type
   FROM pg_foreign_data_wrapper f
UNION ALL
 SELECT n.nspname AS schema,
    t.typname AS name,
    pg_get_userbyid(t.typowner) AS owner,
    'domain'::text AS type
   FROM (pg_type t
     JOIN pg_namespace n ON ((n.oid = t.typnamespace)))
  WHERE ((t.typtype = 'd'::"char") AND (n.nspname <> 'pg_catalog'::name) AND (n.nspname <> 'information_schema'::name))
UNION ALL
 SELECT NULL::name AS schema,
    l.lanname AS name,
    pg_get_userbyid(l.lanowner) AS owner,
    'language'::text AS type
   FROM pg_language l
  WHERE (l.lanplcallfoid <> (0)::oid)
UNION ALL
 SELECT NULL::name AS schema,
    t.spcname AS name,
    pg_get_userbyid(t.spcowner) AS owner,
    'tablespace'::text AS type
   FROM pg_tablespace t;

ALTER TABLE standard.show_object_ownership OWNER TO postgres;


CREATE OR REPLACE VIEW standard.show_object_privileges AS
 SELECT z.schema,
    z.name,
    z.owner,
    z.type,
    z.objuser,
    z.privilege_aggregate,
    z.privilege,
        CASE z.privilege
            WHEN '*'::text THEN 'GRANT'::text
            WHEN 'r'::text THEN 'SELECT'::text
            WHEN 'w'::text THEN 'UPDATE'::text
            WHEN 'a'::text THEN 'INSERT'::text
            WHEN 'd'::text THEN 'DELETE'::text
            WHEN 'D'::text THEN 'TRUNCATE'::text
            WHEN 'x'::text THEN 'REFERENCES'::text
            WHEN 't'::text THEN 'TRIGGER'::text
            WHEN 'X'::text THEN 'EXECUTE'::text
            WHEN 'U'::text THEN 'USAGE'::text
            WHEN 'C'::text THEN 'CREATE'::text
            WHEN 'c'::text THEN 'CONNECT'::text
            WHEN 'T'::text THEN 'TEMPORARY'::text
            ELSE ('Unknown: '::text || z.privilege)
        END AS privilege_pretty
   FROM ( SELECT y.schema,
            y.name,
            y.owner,
            y.type,
                CASE
                    WHEN (NOT (COALESCE(y.objuser, ''::text) IS DISTINCT FROM ''::text)) THEN 'public'::text
                    ELSE y.objuser
                END AS objuser,
            regexp_split_to_table(y.privilege_aggregate, '\s*'::text) AS privilege,
            y.privilege_aggregate
           FROM ( SELECT x.schema,
                    x.name,
                    x.owner,
                    x.type,
                    regexp_replace(x.privileges, '/.*'::text, ''::text) AS privileges,
                    (regexp_split_to_array(regexp_replace(x.privileges, '/.*'::text, ''::text), '='::text))[1] AS objuser,
                    (regexp_split_to_array(regexp_replace(x.privileges, '/.*'::text, ''::text), '='::text))[2] AS privilege_aggregate
                   FROM ( SELECT NULL::name AS schema,
                            (n.nspname)::text AS name,
                            pg_get_userbyid(n.nspowner) AS owner,
                            'schema'::text AS type,
                            regexp_split_to_table(array_to_string(n.nspacl, ','::text), ','::text) AS privileges
                           FROM pg_namespace n
                          WHERE ((n.nspname !~ '^pg_'::text) AND (n.nspname <> 'information_schema'::name))
                        UNION ALL
                         SELECT n.nspname AS schema,
                            ((((p.proname)::text || '('::text) || pg_get_function_arguments(p.oid)) || ')'::text) AS name,
                            pg_get_userbyid(p.proowner) AS owner,
                                CASE
                                    WHEN (p.prokind = 'a'::"char") THEN 'aggregate'::text
                                    WHEN (p.prokind = 'w'::"char") THEN 'window'::text
                                    WHEN (p.prorettype = ('trigger'::regtype)::oid) THEN 'function'::text
                                    ELSE 'function'::text
                                END AS type,
                            regexp_split_to_table(array_to_string(p.proacl, ','::text), ','::text) AS privileges
                           FROM (pg_proc p
                             JOIN pg_namespace n ON ((n.oid = p.pronamespace)))
                          WHERE ((n.nspname <> 'pg_catalog'::name) AND (n.nspname <> 'information_schema'::name))
                        UNION ALL
                         SELECT n.nspname AS schema,
                            (c.relname)::text AS name,
                            pg_get_userbyid(c.relowner) AS owner,
                                CASE c.relkind
                                    WHEN 'r'::"char" THEN 'table'::text
                                    WHEN 'v'::"char" THEN 'view'::text
                                    WHEN 'm'::"char" THEN 'materialized view'::text
                                    WHEN 'i'::"char" THEN 'index'::text
                                    WHEN 'S'::"char" THEN 'sequence'::text
                                    WHEN 'f'::"char" THEN 'foreign table'::text
                                    WHEN 'c'::"char" THEN 'type'::text
                                    ELSE NULL::text
                                END AS type,
                            regexp_split_to_table(array_to_string(c.relacl, ','::text), ','::text) AS privileges
                           FROM (pg_class c
                             JOIN pg_namespace n ON ((n.oid = c.relnamespace)))
                          WHERE ((n.nspname <> 'pg_catalog'::name) AND (n.nspname <> 'information_schema'::name) AND (n.nspname !~ '^pg_toast'::text))
                        UNION ALL
                         SELECT NULL::name AS schema,
                            (s.srvname)::text AS name,
                            pg_get_userbyid(s.srvowner) AS owner,
                            'foreign server'::text AS type,
                            regexp_split_to_table(array_to_string(s.srvacl, ','::text), ','::text) AS privileges
                           FROM pg_foreign_server s
                        UNION ALL
                         SELECT NULL::name AS schema,
                            (f.fdwname)::text AS name,
                            pg_get_userbyid(f.fdwowner) AS owner,
                            'foreign data wrapper'::text AS type,
                            regexp_split_to_table(array_to_string(f.fdwacl, ','::text), ','::text) AS privileges
                           FROM pg_foreign_data_wrapper f
                        UNION ALL
                         SELECT n.nspname AS schema,
                            t.typname AS name,
                            pg_get_userbyid(t.typowner) AS owner,
                            'domain'::text AS type,
                            regexp_split_to_table(array_to_string(t.typacl, ','::text), ','::text) AS privileges
                           FROM (pg_type t
                             JOIN pg_namespace n ON ((n.oid = t.typnamespace)))
                          WHERE ((t.typtype = 'd'::"char") AND (n.nspname <> 'pg_catalog'::name) AND (n.nspname <> 'information_schema'::name))
                        UNION ALL
                         SELECT NULL::name AS schema,
                            l.lanname AS name,
                            pg_get_userbyid(l.lanowner) AS owner,
                            'language'::text AS type,
                            regexp_split_to_table(array_to_string(l.lanacl, ','::text), ','::text) AS privileges
                           FROM pg_language l
                          WHERE (l.lanplcallfoid <> (0)::oid)
                        UNION ALL
                         SELECT NULL::name AS schema,
                            t.spcname AS name,
                            pg_get_userbyid(t.spcowner) AS owner,
                            'tablespace'::text AS type,
                            regexp_split_to_table(array_to_string(t.spcacl, ','::text), ','::text) AS privileges
                           FROM pg_tablespace t) x) y) z;

ALTER TABLE standard.show_object_privileges OWNER TO postgres;


GRANT EXECUTE ON FUNCTION standard.anchored_column() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.distinct_update() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.distinct_update_modified() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.get_userid() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.history_trigger() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.modified() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.refresh_materialized_view(_schemaname text, _matviewname text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.standardize_table_history_and_trigger(v_root_schema text, v_table text) TO PUBLIC;

COMMIT;
