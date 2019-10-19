from . import BaseCommand
from termcolor import colored
import urllib.parse
import traceback
import json


class AssignCommand(BaseCommand):
    def run(self, fqdn, process_name, process_environment, **kwargs):
        try:
            data = {
                "op": "add",
                "path": "/assignments",
                "value": {
                    "name": process_name,
                    "environment": process_environment
                }
            }

            # patch the configuration
            url = "{}/tool/v1/hosts/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
            response = self.dart_api.patch(url, data=json.dumps(data), timeout=10)

            # catch expected errors
            if (response.status_code in [400, 404]):
                print("{} Could not assign {} in {} to {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, process_environment, fqdn, data.get("StatusDescription") or "Unknown error."))
                return 1

            # catch any other errors
            response.raise_for_status()

            # now tell the host to update its configurations
            try:
                url = "{}/coordination/v1/rewrite/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
                response = self.dart_api.post(url, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print("{} Could not send rewrite command to {}: {}".format(colored("WARNING!", "yellow", attrs=["bold"]), fqdn, e))

            print("{} Assigned {} in {} to {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process_name, process_environment, fqdn))
            return 0
        except Exception as e:
            print("{} Could not assign {} in {} to {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, process_environment, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class UnassignCommand(BaseCommand):
    def run(self, fqdn, process_name, **kwargs):
        try:
            data = {
                "op": "remove",
                "path": "/assignments",
                "value": {
                    "name": process_name,
                }
            }

            # patch the configuration
            url = "{}/tool/v1/hosts/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
            response = self.dart_api.patch(url, data=json.dumps(data), timeout=10)

            # catch expected errors
            if (response.status_code in [400, 404]):
                print("{} Could not unassign {} from {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, fqdn, data.get("StatusDescription") or "Unknown error."))
                return 1

            # catch any other errors
            response.raise_for_status()

            # now tell the host to update its configurations
            try:
                url = "{}/coordination/v1/rewrite/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
                response = self.dart_api.post(url, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print("{} Could not send rewrite command to {}: {}".format(colored("WARNING!", "yellow", attrs=["bold"]), fqdn, e))

            print("{} Unassigned {} from {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process_name, fqdn))
            return 0
        except Exception as e:
            print("{} Could not unassign {} from {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1
