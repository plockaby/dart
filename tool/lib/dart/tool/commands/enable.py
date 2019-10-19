from . import BaseCommand
from termcolor import colored
import urllib.parse
import traceback
import json


class EnableCommand(BaseCommand):
    def run(self, fqdn, process_name, **kwargs):
        try:
            data = {
                "op": "replace",
                "path": "/assignments",
                "value": {
                    "fqdn": fqdn,
                    "disabled": False
                }
            }

            # patch the configuration
            url = "{}/tool/v1/processes/{}".format(self.dart_api_url, urllib.parse.quote(process_name))
            response = self.dart_api.patch(url, data=json.dumps(data), timeout=10)

            # catch expected errors
            if (response.status_code in [400, 404]):
                print("{} Could not enable {} on {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, fqdn, data.get("StatusDescription") or "Unknown error."))
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

            print("{} Enabled {} on {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process_name, fqdn))
            return 0
        except Exception as e:
            print("{} Could not enable {} on {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1


class DisableCommand(BaseCommand):
    def run(self, fqdn, process_name, **kwargs):
        try:
            data = {
                "op": "replace",
                "path": "/assignments",
                "value": {
                    "fqdn": fqdn,
                    "disabled": True
                }
            }

            # patch the configuration
            url = "{}/tool/v1/processes/{}".format(self.dart_api_url, urllib.parse.quote(process_name))
            response = self.dart_api.patch(url, data=json.dumps(data), timeout=10)

            # catch expected errors
            if (response.status_code in [400, 404]):
                print("{} Could not disable {} on {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, fqdn, data.get("StatusDescription") or "Unknown error."))
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

            print("{} Disabled {} on {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), process_name, fqdn))
            return 0
        except Exception as e:
            print("{} Could not disable {} on {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), process_name, fqdn, e))
            self.logger.debug(traceback.format_exc())
            return 1
