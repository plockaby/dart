CREATE SCHEMA IF NOT EXISTS standard;
GRANT USAGE ON SCHEMA standard TO PUBLIC;


CREATE OR REPLACE FUNCTION standard.prohibit_change() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*
    Function:     standard.prohibit_change()
    Description:  Apply to any table as a BEFORE trigger when you don't want
                  anything changed on the table. Useful for preventing updates
                  and deletes and I guess maybe inserts if you want to lock a
                  table from being modified in any way.
    Affects:      Prevents a change
    Arguments:    none
    Returns:      trigger
*/
DECLARE
BEGIN
    -- returning NULL cancels whatever operation was happening on the row
    RETURN NULL;
END;
$$;


CREATE OR REPLACE FUNCTION standard.anchored_column() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*
    Function:     standard.anchored_column(p_column_name)
    Description:  Trigger function prevent a
                  particular column value.
    Affects:      Raises an ERROR an an attempt to modify the specified column,
                  otherwise does not modify data.
    Arguments:    none
    Returns:      new (the updated row)
*/
DECLARE
    -- triggers cannot have declared arguments but we can get arguments from
    -- the caller by using TG_ARGV
    p_column_name TEXT := TG_ARGV[0];

    -- variables that we use
    v_old TEXT;
    v_new TEXT;
BEGIN
    EXECUTE 'SELECT ('||quote_literal(OLD)||'::'||TG_RELID::regclass||').'||quote_ident(p_column_name) INTO v_old;
    EXECUTE 'SELECT ('||quote_literal(NEW)||'::'||TG_RELID::regclass||').'||quote_ident(p_column_name) INTO v_new;

    IF quote_ident(v_old) != quote_ident(v_new) THEN
        RAISE EXCEPTION 'column "%" may not be changed', p_column_name;
    END IF;

    RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION standard.distinct_update() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*
    Function:     standard.distinct_update()
    Description:  Trigger function that will drop an update that does not
                  modify any column on the row. This will prevent the creation
                  of additional history records. This should be applied as a
                  BEFORE trigger after any other trigger that made a change has
                  been applied.
    Affects:      makes no changes to data
    Arguments:    none
    Returns:      If there are no changes NULL is returned which ends the
                  processing of the update on that specific row. Otherwise NEW
                  is returned (the updated row).
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


CREATE OR REPLACE FUNCTION standard.distinct_update_modified() RETURNS trigger
    LANGUAGE plpgsql
AS $$
/*
    Function:     standard.distinct_update_modified()
    Description:  Trigger function that will drop an update that does not
                  modify any column on the row. This will prevent the creation
                  of additional history records.
    Affects:      makes no changes to data
    Arguments:    none
    Returns:      If there are no changes NULL is returned which ends the
                  processing of the update on that specific row. Otherwise NEW
                  is returned (the updated row).
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


CREATE OR REPLACE FUNCTION standard.get_user_id() RETURNS text
    LANGUAGE plpgsql
AS $$
/*
    Function:     standard.get_user_id()
    Description:  For retrieving the user identity performing the transaction.
                  Useful as the default value for modified_by or created_by
                  columns. See code below example of the usage.
    Affects:      makes no changes to data
    Arguments:    none
    Returns:      text with the identity of the current actor
    Usage:

        BEGIN;
        SET LOCAL local.userid TO {value};

        {SQL to run}

        COMMIT;
*/
DECLARE
    v_user_id TEXT;
BEGIN
    v_user_id := current_setting('local.userid');
    IF v_user_id IS NULL or v_user_id ~ E'^\\s*$' THEN
        RETURN CURRENT_USER;
    END IF;
    RETURN v_user_id;
EXCEPTION
    WHEN OTHERS THEN RETURN CURRENT_USER;
END;
$$;


CREATE OR REPLACE FUNCTION standard.history_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
AS $$
/*
    Function:     standard.history_trigger()
    Description:  Standard history trigger function which will take the values
                  from an INSERT, UPDATE, DELETE, or TRUNCATE and insert into
                  the appropriate history table. This function requires:

                  1) the base table have the following columns:
                    *) "modified_at  timestamp with time zone"
                    *) "modified_by  text"
                  2) the history table must
                    *) have the same name as the base table
                    *) be in the schema "{base table schema}_history"
                    *) have its first column be modified_action TEXT NOT NULL
                    *) have its second column be txn_timestamp TIMESTAMP WITH TIME ZONE
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
    v_parent_table     TEXT;
    v_history_table    TEXT;
    v_modified_action  TEXT;
    v_transaction_time TIMESTAMP WITH TIME ZONE;
BEGIN
    v_parent_table := TG_TABLE_SCHEMA||'.'||TG_TABLE_NAME;
    v_history_table := TG_TABLE_SCHEMA||'.'||TG_TABLE_NAME||'_history';
    v_modified_action := TG_OP;
    v_transaction_time := transaction_timestamp();

    IF TG_OP = 'DELETE' THEN
        -- reset these to now instead of what was already in the deleted column
        OLD.modified_at := statement_timestamp();
        OLD.modified_by := standard.get_user_id();
        EXECUTE 'INSERT INTO '||v_history_table||' SELECT $1, $2, $3.*'
            USING v_modified_action, v_transaction_time, OLD;
        RETURN OLD;

    ELSIF TG_OP = 'TRUNCATE' THEN
        -- everything but these four columns is NULL
        EXECUTE 'INSERT INTO '||v_history_table||' (modified_action, txn_timestamp, modified_at, modified_by) VALUES ($1, $2, $3, $4)'
            USING v_modified_action, v_transaction_time, statement_timestamp(), standard.get_user_id();
        RETURN NULL;

    ELSE
        EXECUTE 'INSERT INTO '||v_history_table||' SELECT $1, $2, $3.*'
            USING v_modified_action, v_transaction_time, NEW;
        RETURN NEW;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION standard.modified() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
/*
    Function:     standard.modified()
    Description:  Trigger function for UPDATEs and INSERTs that sets the
                  modified_at column to statement_timestamp() and the
                  modified_by column to standard.get_user_id().
    Affects:      Modifies the NEW row as described above.
    Arguments:    none
    Returns:      The NEW row.
*/
DECLARE
BEGIN
    new.modified_at := statement_timestamp();
    new.modified_by := standard.get_user_id();
    RETURN new;
END;
$$;



CREATE OR REPLACE FUNCTION standard.refresh_materialized_view(v_schema_name text, v_view_name text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
    v_test_ownership  BOOLEAN;
    v_test_concurrent BOOLEAN;
BEGIN
    -- if we don't own the materialized view then we can't update it
    v_test_ownership = (
        SELECT true
        FROM pg_catalog.pg_matviews
        WHERE schemaname = v_schema_name
          AND matviewname = v_view_name
          AND matviewowner = current_user
    );

    IF (NOT v_test_ownership) THEN
        RAISE EXCEPTION 'materialized view does not exist or is not updateable';
    END IF;

    -- if the materialized view has a unique key then we can update concurrently
    v_test_concurrent = (
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
          AND x.schema_name = v_schema_name
          AND x.table_name = v_view_name
          AND x.is_unique IS TRUE
    );

    IF (v_test_concurrent) THEN
        EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || quote_ident(v_schema_name) || '.' || quote_ident(v_view_name);
    ELSE
        EXECUTE 'REFRESH MATERIALIZED VIEW ' || quote_ident(v_schema_name) || '.' || quote_ident(v_view_name);
    END IF;

    RETURN;
END;
$$;


CREATE OR REPLACE FUNCTION standard.standardize_table_history_and_trigger(v_schema_name text, v_table_name text) RETURNS void
    LANGUAGE plpgsql
AS $$
/*  Function:     standard.standardize_table_history_and_trigger(schema_name, table_name)
    Description:  Function that will create the necessary history table for a
                  given table.
    Affects:      Creates a new table in "schema_name" called
                  "table_name_history". Creates triggers on provided table.
    Arguments:    text v_schema_name - name of schema the source table lives in
                  text v_table_name  - name of source table
    Returns:      void

    SELECT standard.standardize_table_history_and_trigger('the_schema', 'the_table');
*/
DECLARE
    v_parent_schema      TEXT;
    v_parent_table       TEXT;   -- original table name without schema
    v_parent_full_table  TEXT;   -- original table name with schema
    v_history_schema     TEXT;
    v_history_table      TEXT;   -- history table name with schema
    v_column             TEXT;
BEGIN
    v_parent_schema := quote_ident(v_schema_name);
    v_parent_table := quote_ident(v_table_name);
    v_parent_full_table := v_parent_schema||'.'||v_parent_table;
    v_history_schema := v_parent_schema;
    v_history_table := v_history_schema||'.'||v_parent_table||'_history';

    -- add history table
    EXECUTE 'CREATE TABLE '||v_history_table||' (modified_action TEXT NOT NULL, txn_timestamp TIMESTAMP WITH TIME ZONE NOT NULL, LIKE '||v_parent_full_table||');';

    -- drop NOT NULL constraints on history table
    FOR v_column IN
        SELECT column_name FROM information_schema.columns
            WHERE table_schema = v_history_schema
                AND table_name = v_parent_table
                AND column_name NOT IN ('modified_action', 'txn_timestamp')
                AND is_nullable = 'NO' LOOP

        EXECUTE 'ALTER TABLE '||v_history_table||' ALTER COLUMN '||v_column||' DROP NOT NULL';

        IF v_column = 'id' THEN
            EXECUTE 'CREATE TRIGGER t10_anchored_column BEFORE UPDATE ON '||v_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.anchored_column(''id'')';
        END IF;
    END LOOP;

    EXECUTE 'GRANT SELECT ON '||v_history_table||' to PUBLIC';

    -- create triggers
    EXECUTE 'CREATE TRIGGER t50_distinct_update_modified BEFORE UPDATE ON '||v_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.distinct_update_modified()';
    EXECUTE 'CREATE TRIGGER t60_modified BEFORE INSERT OR UPDATE ON '||v_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.modified()';
    EXECUTE 'CREATE TRIGGER t90_history_saver AFTER INSERT OR UPDATE OR DELETE ON '||v_parent_full_table||' FOR EACH ROW EXECUTE PROCEDURE standard.history_trigger()';
    EXECUTE 'CREATE TRIGGER t90_history_saver_truncate AFTER TRUNCATE ON '||v_parent_full_table||' FOR EACH STATEMENT EXECUTE PROCEDURE standard.history_trigger()';
END;
$$;


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


GRANT EXECUTE ON FUNCTION standard.prohibit_change() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.anchored_column() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.distinct_update() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.distinct_update_modified() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.get_user_id() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.history_trigger() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.modified() TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.refresh_materialized_view(TEXT, TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION standard.standardize_table_history_and_trigger(TEXT, TEXT) TO PUBLIC;
