# NAME

dart

# DESCRIPTION

This is a set of programs that work with [Supervisor](http://supervisord.org/)
to control and monitor processes on multiple hosts. It uses RabbitMQ for
coordination and communication. It uses Cassandra for distributed and fault
tolerant data storage. There are six components:

## agent

This program runs as an event listener inside of supervisord on every host that
is to be controlled by dart. It starts and stops program on schedules and on
demand. It monitors the programs running on the host. It reports back to the
dart processors the state of supervisord on every host.

## tool

This program is used to get the status of hosts and processes controlled by
dart. It lists hosts, processes, host information, and process information.

## config

This program is used to register processes with dart and to otherwise provide a
CLI API to the dart system. This is the only way to send programs to dart using
the dartrc file example.

## backup

This program can be used to backup the configurations that are in dart and is
significantly easier to use than any Cassandra backup. It also works to restore
any and all data into the dart system.

## processor

This program is a set of daemons that listen for messages from each agent and
update the dart system with things like active processes, pending changes, and
other configuration details from each host.

## web

This is a web application that provides a more transparent and visual way to
access the dart system when compared to the `tool` described above. It requires
Apache or Nginx to be configured to proxy requests to a Flask daemon.

# CREDITS

This program is based on a system of the same name used by the University of
Washington's Information Technology department. The code you see here has been
developed by Paul Lockaby.
