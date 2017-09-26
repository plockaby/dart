#!/usr/bin/env python3
"""
This is a processor for events coming off of the message bus. It listens for
things such as:

* State events.
* Active configuration events.
* Pending configuration events.
* Probe events.
"""

import sys
import argparse
import logging
import logging.handlers
import traceback


def main():
    parser = argparse.ArgumentParser(
        prog="dart-processor",
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
    subparsers = parser.add_subparsers(title="command", description="which dart processor component to run", dest="command", metavar="COMMAND")
    subparsers.required = True

    # options for the "state" command
    subparser = subparsers.add_parser("state", help="process state events")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

    # options for the "active" command
    subparser = subparsers.add_parser("active", help="process active configuration events")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

    # options for the "pending" command
    subparser = subparsers.add_parser("pending", help="process pending configuration events")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

    # options for the "probe" command
    subparser = subparsers.add_parser("probe", help="process configuration probe events")
    subparser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")

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

        if (command == "state"):
            from .processors.state import StateProcessor
            runnable = StateProcessor(**configuration)

        if (command == "active"):
            from .processors.active import ActiveConfigurationProcessor
            runnable = ActiveConfigurationProcessor(**configuration)

        if (command == "pending"):
            from .processors.pending import PendingConfigurationProcessor
            runnable = PendingConfigurationProcessor(**configuration)

        if (command == "probe"):
            from .processors.probe import ProbeProcessor
            runnable = ProbeProcessor(**configuration)

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
