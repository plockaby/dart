from . import DataCommand
from termcolor import colored
import dart.common.query
import dart.common.exceptions
import traceback


class HostTagsCommand(DataCommand):
    def run(self, **kwargs):
        try:
            print(colored("{:<80}".format("Host Tags"), "grey", "on_white", attrs=["bold"]))

            tags = dart.common.query.host_tags()
            if (len(tags)):
                for tag, fqdns in sorted(tags.items()):
                    print(colored(tag, "white", attrs=["bold"]))
                    for fqdn in sorted(fqdns):
                        print(" * {}".format(fqdn))
                    print("")
            else:
                print(" No tags have been assigned to any hosts.")

            return 0
        except Exception as e:
            print("{} Could not get the list of tags assigned to hosts: {}".format(colored("FAILURE!", "red", attrs=["bold"]), e))
            self.logger.debug(traceback.format_exc())
            return 1


class TagHostCommand(DataCommand):
    def run(self, fqdn, tag, **kwargs):
        try:
            dart.common.query.add_host_tag(fqdn, tag.strip())
            print("{} Added tag {} to host named {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), tag, fqdn))
            return 0
        except dart.common.exceptions.DartInvalidTagException as e:
            print("{} Could not add tag '{}' to {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), tag, fqdn, e))
            return 1
        except dart.common.exceptions.DartHostDoesNotExistException as e:
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1
        except Exception as e:
            print("{} Could not add tag {} to host named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), tag, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class UntagHostCommand(DataCommand):
    def run(self, fqdn, tag, **kwargs):
        try:
            dart.common.query.remove_host_tag(fqdn, tag.strip())
            print("{} Removed tag {} from host named {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), tag, fqdn))
            return 0
        except dart.common.exceptions.DartHostDoesNotExistException as e:
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1
        except Exception as e:
            print("{} Could not remove tag {} from host named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, tag, e))
            self.logger.debug(traceback.format_exc())
            return 1
