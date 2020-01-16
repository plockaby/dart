#!/bin/bash

PGUSER="postgres"
PGHOST="postgres"
PGDATABASE="dart"

SCRIPT_PATH=`dirname $(readlink -f $0)`
SCHEMA_FILES=`ls $SCRIPT_PATH/schema/*.sql | sort | tr '\n' ' '`

while getopts ":U:h:d:p" arg; do
    case $arg in
        U) PGUSER=$OPTARG;;
        h) PGHOST=$OPTARG;;
        d) PGDATABASE=$OPTARG;;
        *) break;;
    esac
done

echo "connecting to $PGDATABASE on $PGHOST as $PGUSER"

# export these to avoid sending them to every psql call
export PGDATABASE
export PGUSER
export PGHOST

echo "creating dart user"
psql -q -X -c "CREATE ROLE dart WITH LOGIN";
psql -q -X -c "GRANT CONNECT ON DATABASE $PGDATABASE TO dart";

echo "loading schema files: $SCHEMA_FILES"
cat $SCHEMA_FILES | psql -q -X
