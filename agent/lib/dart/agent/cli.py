#!/usr/bin/env python3
"""
This is a supervisord event listener. It does things such as:

* Forward state changes to the distributed data store.
* Forward active and pending configurations to the distributed data store.
* Forward host configuration information to the distributed data store.
* Listen for commands to execute against supervisord.
* Start processes on a schedule.
* Update the scheduler configuration from the distributed data store.
* Update the supervisord configuration from the distributed data store.
* Update the monitor configuration from the distributed data store.
* Monitors process logs and generates events from matching lines.
* Monitors process state and generates events from those changes.
"""

import sys
import argparse
import logging
import logging.handlers
import traceback


def main():
    parser = argparse.ArgumentParser(
        prog="dart-agent",
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    args = parser.parse_args()

    # configure logging
    logging.captureWarnings(True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    log_handler = logging.handlers.SysLogHandler(address="/dev/log")
    log_handler.setFormatter(logging.Formatter("dart-agent[%(process)d]: %(asctime)s %(levelname)-8s - %(message)s"))
    logger.addHandler(log_handler)

    # change the level and output format if we're going to be verbose
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        log_handler.setFormatter(logging.Formatter("dart-agent[%(process)d]: %(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s"))

    # start the main program
    try:
        options = vars(args)
        configuration = dict(verbose=options.pop("verbose"))

        from .app import DartAgent
        runnable = DartAgent(**configuration)
        return runnable.run(**options)
    except Exception as e:
        logger.error(str(e))
        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
