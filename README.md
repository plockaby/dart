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

## tool

This is a command line tool to control the Dart system. It can be used to view,
control, and modify the data in the Dart system.

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

Each component requires the `dart-common` library. However, since no parts of
this application are on PyPi the dependency system will not automatically
include `dart-common` when you run `python setup.py install` so be sure to
install the `dart-common` package first.

The `agent` and `tool` components will each create their own binaries called
`dart-agent` and `dart`, respectively. Those are the entry points for those
applications.

However, for the `api` and `portal` applications you will need either a large
pile of dependencies installed or you will need a virtual environment. Either
way you can start them like this:

```
gunicorn dart.api.loader:app --worker-class=gevent -b 8001
gunicorn dart.portal.loader:app --worker-class=gevent -b 8002
```

You should change the arguments to match your preferences. Things that you
might want to change include: the port number and the logging configuration.

It's worth noting that at this time the `eventlet` worker class is not
supported. There is a bug in `eventlet` that prevents it from correctly using
client certificates on SSL connections. It is recommended that you use gevent
instead.

# CREDITS

This program is based on a system of the same name used by the University of
Washington's Information Technology department. The code you see here has been
developed by Paul Lockaby.
