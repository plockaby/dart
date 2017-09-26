from . import DataCommand
from termcolor import colored
import dart.common.remote
import dart.common.query
import dart.common.exceptions
import traceback


class AssignCommand(DataCommand):
    def run(self, fqdn, process, environment, **kwargs):
        try:
            # make the association
            dart.common.query.assign(process, environment, fqdn)

            # now tell the host to update
            dart.common.remote.command(fqdn, "rewrite")

            print("{} Assigned {} in {} to {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process, environment, fqdn))
            return 0
        except dart.common.exceptions.DartProcessEnvironmentDoesNotExistException as e:
            print("{} No process named {} in {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process, environment))
            return 1
        except dart.common.exceptions.DartHostDoesNotExistException as e:
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1
        except Exception as e:
            print("{} Could not assign {} in {} to {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, environment, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class UnassignCommand(DataCommand):
    def run(self, fqdn, process, **kwargs):
        try:
            # remove the association
            dart.common.query.unassign(process, fqdn)

            # now tell the host to update
            dart.common.remote.command(fqdn, "rewrite")

            print("{} Unassigned {} from {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process, fqdn))
            return 0
        except dart.common.exceptions.DartProcessDoesNotExistException as e:
            print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process))
            return 1
        except dart.common.exceptions.DartHostDoesNotExistException as e:
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1
        except Exception as e:
            print("{} Could not unassign {} from {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class EnableCommand(DataCommand):
    def run(self, fqdn, process, **kwargs):
        try:
            # remove the association
            dart.common.query.enable(process, fqdn)

            # now tell the host to update
            dart.common.remote.command(fqdn, "rewrite")

            print("{} Enabled {} on {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process, fqdn))
            return 0
        except dart.common.exceptions.DartProcessNotAssignedException as e:
            print("{} The process named {} is not currently assigned to the host {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, fqdn))
            return 1
        except dart.common.exceptions.DartProcessDoesNotExistException as e:
            print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process))
            return 1
        except dart.common.exceptions.DartHostDoesNotExistException as e:
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1
        except Exception as e:
            print("{} Could not enable {} on {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class DisableCommand(DataCommand):
    def run(self, fqdn, process, **kwargs):
        try:
            # remove the association
            dart.common.query.disable(process, fqdn)

            # now tell the host to update
            dart.common.remote.command(fqdn, "rewrite")

            print("{} Disabled {} on {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process, fqdn))
            return 0
        except dart.common.exceptions.DartProcessNotAssignedException as e:
            print("{} The process named {} is not currently assigned to the host {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, fqdn))
            return 1
        except dart.common.exceptions.DartProcessDoesNotExistException as e:
            print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process))
            return 1
        except dart.common.exceptions.DartHostDoesNotExistException as e:
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1
        except Exception as e:
            print("{} Could not disable {} on {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1
