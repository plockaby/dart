from . import BaseCommand
from termcolor import colored
import sys
import yaml
import traceback
import json


class RegisterCommand(BaseCommand):
    def run(self, path, **kwargs):
        body = None

        try:
            if (path == "-"):
                body = yaml.load(sys.stdin.read(), Loader=yaml.SafeLoader)
            else:
                with open(path, "r") as f:
                    body = yaml.load(f.read(), Loader=yaml.SafeLoader)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, Exception) as e:
            print("{} Could not load {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), path, e))
            self.logger.debug(traceback.format_exc())
            raise 1

        if (body is None):
            print("{} Could not load {}: found no valid configurations.".format(colored("FAILURE!", "red", attrs=["bold"]), path))
            return 1

        try:
            print("Sending registration request using {}.".format(path))
            url = "{}/tool/v1/register".format(self.dart_api_url)
            response = self.dart_api.post(url, data=json.dumps(body), timeout=60)
            data = response.json()

            # try to print something helpful
            if (response.status_code != 200):
                print("{} Could not load {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), path, data.get("message") or "Unknown error."))
                return 1

            # then raise the exception to abort the system
            response.raise_for_status()

            # print what we just registered
            for process in response.json()["registered"]:
                print("* Registered {} named {} in {}.".format(process["type"], process["name"], process["environment"]))

            # success
            print("{} Finished loading {} into dart.".format(colored("SUCCESS!", "green", attrs=["bold"]), path))
            return 0
        except Exception as e:
            print("{} Could not load {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), path, e))
            self.logger.debug(traceback.format_exc())
            return 1
