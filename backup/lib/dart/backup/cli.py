#!/usr/bin/env python3
"""
This is a tool that does automated exports and imports of dart data for backups
and restorations.

* backup
  This will create a backup file containing all information needed to rebuild
  the dart system. By default a backup does NOT include transient data that can
  be rebuilt by the system such as active processes or server lists. If you
  want to backup ALL data then use the --everything flag.

* restore <filename.json>
  This will restore the database from a backup file. By default a restoration
  will append to the data already present. If you wish to replace the data that
  is already there then use the --truncate flag.
"""

import sys
import argparse
import logging
import logging.handlers
import traceback


def main():
    parser = argparse.ArgumentParser(
        prog="dart-backup",
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparsers = parser.add_subparsers(title="command", description="which dart component to run", dest="command", metavar="COMMAND")
    subparsers.required = True

    # options for the "backup" command
    subparser = subparsers.add_parser("backup", help="export a backup configuration")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("-e", "--everything", dest="everything", action="store_true", default=False, help="export everything")

    # options for the "restore" command
    subparser = subparsers.add_parser("restore", help="import a backup configuration")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparser.add_argument("--truncate", dest="truncate", action="store_true", default=False, help="empty tables before loading new data")
    subparser.add_argument("file", help="path to file to import (use - to read from stdin)")

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

        if (command == "backup"):
            from .commands.backup import BackupCommand
            runnable = BackupCommand(**configuration)

        if (command == "restore"):
            from .commands.restore import RestoreCommand
            runnable = RestoreCommand(**configuration)

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
