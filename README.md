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

## api

This is the API that is used by the other components to interact with the
database. It can be used programmatically for additional tools as well.

## portal

This program is used to get the status of hosts and processes controlled by
dart. It can be used to interact with the API. It requires a web server to be
configured to proxy requests to a Flask program running inside an application
server such as gunicorn.

# CREDITS

This program is based on a system of the same name used by the University of
Washington's Information Technology department. The code you see here has been
developed by Paul Lockaby.
