#!/usr/bin/env python3
"""
This is a tool that provides configuration information about dart and its
components. This tool is used by other command line tools to access dart
through more programmatically amenable means.

* hosts
  Returns a JSON document containing default information about all hosts.

* register
  Processes a .dartrc file to register a host in the system.
"""

import sys
import argparse
import logging
import logging.handlers
import traceback


def main():
    parser = argparse.ArgumentParser(
        prog="dart-config",
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparsers = parser.add_subparsers(title="command", description="which dart component to run", dest="command", metavar="COMMAND")
    subparsers.required = True

    # options for the "hosts" command
    subparser = subparsers.add_parser("hosts", help="details about all hosts")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

    # options for the "register" command
    subparser = subparsers.add_parser("register", help="register process configuration")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("file", help="path to file to register (use - to read from stdin)")

    args = parser.parse_args()

    # configure logging
    logging.captureWarnings(True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    log_handler = logging.StreamHandler(stream=sys.stdout)
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

        if (command == "hosts"):
            from .commands.host import HostsCommand
            runnable = HostsCommand(**configuration)

        if (command == "register"):
            from .commands.register import RegisterCommand
            runnable = RegisterCommand(**configuration)

        # now that we've imported our generic tool, run it
        if (runnable is not None):
            runnable.run(**options)

        return 0
    except Exception as e:
        logger.error(str(e))
        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
