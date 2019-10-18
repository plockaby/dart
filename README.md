# NAME

dart

# DESCRIPTION

This is a set of programs that work with [Supervisor](http://supervisord.org/)
to control and monitor processes on multiple hosts.

## agent

This program runs as an event listener inside of supervisord on every host that
is to be controlled by dart. It starts and stops program on schedules and on
demand. It monitors the programs running on the host. It reports back to the
dart on the state of supervisord on every host.

## registrar

This program reads a `.dartrc` file and sends it to the API to register a new
program with the dart system. This is a helper program to demonstrate how to
use the API.

## api

This is the API that is used by the other components to interact with the
database. It can be used programmatically for additional tools as well.

## portal

This program is used to get the status of hosts and processes controlled by
dart. It can be used to interact with the API. It requires a web server to be
configured to proxy requests to a Flask program running inside an application
server such as gunicorn.

# USAGE

## Creating the Database

The dart system uses a PostgreSQL database. It depends on you loading the two
SQL scripts `dart-standard.sql` and `dart.sql`, in that order.

## Configuring the System

There must exist a settings file. It should be deployed alongside the Python
files under `dart/settings/settings.yaml`. There is an example settings file
in `agent/lib/dart/settings/settings.yaml.example`.

## Running Each Component

The `agent` and `registrar` programs are just Python modules that can be called
by writing a shell script that looks roughly like this:

```
#!/bin/sh
exec python3 -m dart.agent.cli "$@"
```

Obviously `agent` can be replaced with `registrar`. It was decided to not
include these shell scripts with the repository to leave it up to the user how
to call Python and with what arguments.

For the `api` and `portal` applications a virtual environment is necessary to
include all of the components. Then you can write a shell script that looks
roughly like this:

```
#!/bin/bash

# don't create .pyc files
export PYTHONDONTWRITEBYTECODE=1

# select the virtual environment
export VIRTUALENV=/srv/www/venv/dart-api
export PATH=$VIRTUALENV/bin:$PATH

exec $VIRTUALENV/bin/python3 $VIRTUALENV/bin/gunicorn dart.api.loader:app "$@"
```

# CREDITS

This program is based on a system of the same name used by the University of
Washington's Information Technology department. The code you see here has been
developed by Paul Lockaby.
