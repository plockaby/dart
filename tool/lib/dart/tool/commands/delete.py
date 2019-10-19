from . import BaseCommand
from termcolor import colored
import urllib.parse
import traceback


class DeleteHostCommand(BaseCommand):
    def run(self, fqdn, **kwargs):
        try:
            url = "{}/tool/v1/hosts/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
            response = self.dart_api.delete(url, timeout=10)
            data = response.json()

            if (response.status_code == 200):
                print("{} Deleted host named {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), fqdn))
                return 0
            if (response.status_code == 400):
                print("{} Could not delete host named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, data.get("StatusDescription") or "Unknown error."))
                return 1
            if (response.status_code == 404):
                print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
                return 1

            response.raise_for_status()
            return 0
        except Exception as e:
            print("{} Could not delete host named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class DeleteProcessCommand(BaseCommand):
    def run(self, name, environment, **kwargs):
        try:
            if (environment is None):
                url = "{}/tool/v1/processes/{}".format(self.dart_api_url, urllib.parse.quote(name))
                response = self.dart_api.delete(url, timeout=10)
                data = response.json()

                if (response.status_code == 200):
                    print("{} Deleted process named {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), name))
                    return 0
                if (response.status_code == 400):
                    print("{} Could not delete process named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), name, data.get("StatusDescription") or "Unknown error."))
                    return 1
                if (response.status_code == 404):
                    print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), name))
                    return 1

                response.raise_for_status()

            else:
                url = "{}/tool/v1/processes/{}/{}".format(self.dart_api_url, urllib.parse.quote(name), urllib.parse.quote(environment))
                response = self.dart_api.delete(url, timeout=10)
                data = response.json()

                if (response.status_code == 200):
                    print("{} Deleted environment {} for process named {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), environment, name))
                    return 0
                if (response.status_code == 400):
                    print("{} Could not delete environment {} for process named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), environment, name, data.get("StatusDescription") or "Unknown error."))
                    return 1
                if (response.status_code == 404):
                    print("{} No environment {} for process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), environment, name))
                    return 1

                response.raise_for_status()

            return 0
        except Exception as e:
            print("{} Could not delete process named {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), name, e))
            self.logger.debug(traceback.format_exc())
            return 1
