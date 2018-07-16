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
import traceback


def main():
    parser = argparse.ArgumentParser(
        prog="dart-processor",
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help="send verbose output to the console")
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

        from .app import DartProcessor
        runnable = DartProcessor(**configuration)
        return runnable.run(**options)
    except Exception as e:
        logger.error(str(e))
        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
