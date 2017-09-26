from . import DataCommand
from termcolor import colored
import dart.common.query
import traceback


class DeleteHostCommand(DataCommand):
    def run(self, fqdn, **kwargs):
        try:
            # don't want to delete anything that has processes assigned to it
            assigned = dart.common.query.host_assigned(fqdn)
            if (len(assigned)):
                print("{} Could not delete host {}: host has {} assigned to it.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, ", ".join(assigned.keys())))
                return 1

            # now clean it out of tables
            dart.common.query.delete_host(fqdn)
            print("{} Deleted the host named {} from dart.".format(colored("SUCCESS!", "green", attrs=["bold"]), fqdn))

            return 0
        except Exception as e:
            print("{} Could not delete host named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class DeleteProcessCommand(DataCommand):
    def run(self, process, environment, **kwargs):
        try:
            # see if this process is still assigned to a host
            assigned = dart.common.query.process_assigned(process)

            # if we are only deleting a particular environment for a process
            # then filter process assignments on that environment.
            assigned = list(filter(lambda x: environment is None or assigned[x]["environment"] == environment, assigned))

            # don't allow deleting a process that is still assigned to hosts
            if (len(assigned)):
                print("{} Could not delete process named {}: process assigned to {}.".format(colored("FAILURE!", "red", attrs=["bold"]), process, ", ".join(assigned)))
                return 1

            if (environment is not None):
                dart.common.query.delete_process(process, environment)
                print("{} Deleted the environment named {} for process named {} from dart.".format(colored("SUCCESS!", "green", attrs=["bold"]), environment, process))
                return 0
            else:
                dart.common.query.delete_process(process)
                print("{} Deleted the process named {} and all its environments from dart.".format(colored("SUCCESS!", "green", attrs=["bold"]), process))
                return 0
        except Exception as e:
            print("{} Could not delete process named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process, e))
            self.logger.debug(traceback.format_exc())
            return 1
