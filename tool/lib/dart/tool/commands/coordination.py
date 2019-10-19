from . import BaseCommand
from termcolor import colored
import urllib.parse
import dart.common
import traceback


class CoordinationCommand(BaseCommand):
    def send(self, fqdn, action, process_name=None):
        # we aren't going to let anyone do anything to the dart agent
        if (process_name is not None and process_name in dart.common.PROCESSES_TO_IGNORE):
            print("{} No changes may be made to {} using this tool. Please use the host's supervisorctl command.".format(colored("FAILURE!", "red", attrs=["bold"]), process_name))
            return 1

        # validate that the host exists
        if (not self.is_valid_host(fqdn)):
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1

        # validate that this process exists
        if (process_name is not None and not self.is_valid_process(process_name)):
            print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process_name))
            return 1

        try:
            if (process_name):
                url = "{}/coordination/v1/{}/{}/{}".format(self.dart_api_url, urllib.parse.quote(action), urllib.parse.quote(fqdn), urllib.parse.quote(process_name))
                response = self.dart_api.post(url, timeout=10)
                response.raise_for_status()

                print("{} Message sent to {} to {} {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), fqdn, action, process_name))
            else:
                url = "{}/coordination/v1/{}/{}".format(self.dart_api_url, urllib.parse.quote(action), urllib.parse.quote(fqdn))
                response = self.dart_api.post(url, timeout=10)
                response.raise_for_status()

                print("{} Message sent to {} to {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), fqdn, action))
            return 0
        except Exception as e:
            if (process_name):
                print("{} Could not send message to {} to {} {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, action, process_name, e))
            else:
                print("{} Could not send message to {} to {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, action, e))
            self.logger.debug(traceback.format_exc())
            return 1


class StartCommand(CoordinationCommand):
    def run(self, fqdn, process_name, **kwargs):
        return self.send(fqdn, "start", process_name)


class StopCommand(CoordinationCommand):
    def run(self, fqdn, process_name, **kwargs):
        return self.send(fqdn, "stop", process_name)


class RestartCommand(CoordinationCommand):
    def run(self, fqdn, process_name, **kwargs):
        return self.send(fqdn, "restart", process_name)


class UpdateCommand(CoordinationCommand):
    def run(self, fqdn, process_name, **kwargs):
        return self.send(fqdn, "update", process_name)


class RereadCommand(CoordinationCommand):
    def run(self, fqdn, **kwargs):
        return self.send(fqdn, "reread")


class RewriteCommand(CoordinationCommand):
    def run(self, fqdn, **kwargs):
        return self.send(fqdn, "rewrite")
