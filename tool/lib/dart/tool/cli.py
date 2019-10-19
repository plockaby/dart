"""
This is a tool that controls the dart system. It provides these commands:

* register <file>
  Registers a dart configuration file.

* hosts
  Lists all hosts and brief details about those hosts.

* host <fqdn>
  Lists verbose details about a particular host.

* processes
  Lists all processes and brief details about each process.

* process <name>
  Lists verbose details about a particular process.

* assign <process> <environment> <fqdn>
  Assigns a process environment to a host. Only one process environment may be
  assigned to a host at one time. As soon as the assignment change is pushed to
  the host then the process will be marked on the host as "pending add". You
  will need to tell the host to "update" the process.

* unassign <process> <fqdn>
  Unassigns a process from a host. Only one process environment may be assigned
  to a host at one time so you do not need to give the environment name when
  unassigning a process from a host. As soon as the assignment change is pushed
  to the host then the process will be marked on the host as "pending removal".
  You will need to tell the host to "update" the process.

* enable <process> <fqdn>
  Enables a process on a host. When a process is "disabled" it will no longer
  be scheduled to run on that host and any monitoring events that the process
  generates will be ignored and not forwarded to the event monitoring system.

* disable <process> <fqdn>
  Disables a process on a host. When a process is "disabled" it will no longer
  be scheduled to run on that host and any monitoring events that the process
  generates will be ignored and not forwarded to the event monitoring system.

* start <process> <fqdn>
  Starts a process on a host. If the process is not assigned and added to this
  host or if the process is already started then this command will do nothing.

* stop <process> <fqdn>
  Stops a process on a host. If the process is not assigned and added to this
  host or if the process is already stopped then this command will do nothing.

* restart <process> <fqdn>
  Restarts a process on a host. If the process is not assigned and added to
  this host then this command will do nothing. If the process is not running it
  will be started.

* update <process> <fqdn>
  Updates the configuration for a process on a particular host. Note that this
  will stop the process and restart it. If you do not want to stop and restart
  the process at this time then do not run this command.

* reread <fqdn>
  Tells the host to reread its pending configurations. Normally pending
  configurations are updated in the data store once per minute. If you are
  impatient then use this command to get the update faster.

* rewrite <fqdn>
  Tells the host to rewrite its pending configurations. Normally pending
  configurations are written to the host once per minute. If you are impatient
  then use this command to get the update faster.

* delete-host <fqdn>
  Deletes all records about a particular host. If the host still has processes
  assigned to it then you will not be able to delete it until all processes are
  unassigned. Note that if the host is still running an active dart-agent or is
  still configured on ref or is still tagged with an Infrastructure Software
  Tools cluster name in Ymir then most of this information will likely be
  shortly repopulated.

* delete-process <process> [<environment>]
  Deletes all records for a process including configurations, schedules, and
  monitors. If the process is still assigned to any hosts then you will not be
  able to delete it until it is unassigned from all hosts. All environments
  will be deleted unless a specific environment is given.
"""

import sys
import argparse
import logging
import traceback


def main():
    parser = argparse.ArgumentParser(
        prog="dart",
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparsers = parser.add_subparsers(title="command", description="which dart component to run", dest="command", metavar="COMMAND")
    subparsers.required = True

    # register a dart configuration file
    subparser = subparsers.add_parser("register", help="register a dart configuration file")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("path", help="path to file to register (use - to read from stdin)")

    # options for the "hosts" command
    subparser = subparsers.add_parser("hosts", help="details about all hosts")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

    # options for the "host" command
    subparser = subparsers.add_parser("host", help="details about a specific host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "processes" command
    subparser = subparsers.add_parser("processes", help="details about all processes")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

    # options for the "process" command
    subparser = subparsers.add_parser("process", help="details about a specific process")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("name", metavar="process", help="name of process")

    # options for the "assign" command
    subparser = subparsers.add_parser("assign", help="assign a process to a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("process_environment", metavar="environment", help="name of process environment")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "unassign" command
    subparser = subparsers.add_parser("unassign", help="unassign a process from a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "enable" command
    subparser = subparsers.add_parser("enable", help="enable a process on a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "disable" command
    subparser = subparsers.add_parser("disable", help="disable a process on a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "start" command
    subparser = subparsers.add_parser("start", help="start a process on a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "stop" command
    subparser = subparsers.add_parser("stop", help="stop a process on a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "restart" command
    subparser = subparsers.add_parser("restart", help="restart a process on a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "update" command
    subparser = subparsers.add_parser("update", help="update a process configuration on a host")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("process_name", metavar="process", help="name of process")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "reread" command
    subparser = subparsers.add_parser("reread", help="reread a host's supervisor configuration")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "rewrite" command
    subparser = subparsers.add_parser("rewrite", help="rewrite a host's supervisor configuration")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "delete-host" command
    subparser = subparsers.add_parser("delete-host", help="delete a host and all its configurations")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("fqdn", help="fully qualified domain name")

    # options for the "delete-process" command
    subparser = subparsers.add_parser("delete-process", help="remove a process and all its configurations")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("name", metavar="process", help="name of process")
    subparser.add_argument("environment", default=None, nargs="?", help="name of process environment (optional)")

    args = parser.parse_args()

    # configure logging
    logging.captureWarnings(True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    log_handler = logging.StreamHandler(stream=sys.stderr)
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s - %(message)s"))
    logger.addHandler(log_handler)

    # change the level and output format if we're going to be verbose
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s"))

    # start the main program
    try:
        options = vars(args)
        configuration = dict(verbose=options.pop("verbose"))
        command = options.pop("command")
        runnable = None

        if (command == "register"):
            from .commands.register import RegisterCommand
            runnable = RegisterCommand(**configuration)

        if (command == "hosts"):
            from .commands.host import HostsCommand
            runnable = HostsCommand(**configuration)

        if (command == "host"):
            from .commands.host import HostCommand
            runnable = HostCommand(**configuration)

        if (command == "processes"):
            from .commands.process import ProcessesCommand
            runnable = ProcessesCommand(**configuration)

        if (command == "process"):
            from .commands.process import ProcessCommand
            runnable = ProcessCommand(**configuration)

        if (command == "assign"):
            from .commands.assign import AssignCommand
            runnable = AssignCommand(**configuration)

        if (command == "unassign"):
            from .commands.assign import UnassignCommand
            runnable = UnassignCommand(**configuration)

        if (command == "enable"):
            from .commands.enable import EnableCommand
            runnable = EnableCommand(**configuration)

        if (command == "disable"):
            from .commands.enable import DisableCommand
            runnable = DisableCommand(**configuration)

        if (command == "start"):
            from .commands.coordination import StartCommand
            runnable = StartCommand(**configuration)

        if (command == "stop"):
            from .commands.coordination import StopCommand
            runnable = StopCommand(**configuration)

        if (command == "restart"):
            from .commands.coordination import RestartCommand
            runnable = RestartCommand(**configuration)

        if (command == "update"):
            from .commands.coordination import UpdateCommand
            runnable = UpdateCommand(**configuration)

        if (command == "reread"):
            from .commands.coordination import RereadCommand
            runnable = RereadCommand(**configuration)

        if (command == "rewrite"):
            from .commands.coordination import RewriteCommand
            runnable = RewriteCommand(**configuration)

        if (command == "delete-host"):
            from .commands.delete import DeleteHostCommand
            runnable = DeleteHostCommand(**configuration)

        if (command == "delete-process"):
            from .commands.delete import DeleteProcessCommand
            runnable = DeleteProcessCommand(**configuration)

        # now that we've imported our generic tool, run it
        if (runnable is not None):
            return runnable.run(**options)
        else:
            print("Unknown command: {}".format(command))
            return 1
    except Exception as e:
        print("An error occurred while trying to run this tool: {}".format(e))
        logger.debug(traceback.format_exc())
        return 1


if (__name__ == "__main__"):
    sys.exit(main())
