import logging
import pkg_resources
import sys
import yaml
import traceback
import requests
import json


class DartRegistrar:
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # try to load settings
        try:
            # get the data out of the file
            data = pkg_resources.resource_string("dart", "settings/settings.yaml").decode("utf-8", "backslashreplace")

            # convert the settings data from yaml to a python data structure
            # this will definitely throw exceptions if the settings file is invalid
            settings = yaml.load(data, Loader=yaml.SafeLoader)

            # now pull out the "portal" settings. our code should set good defaults.
            self.settings = settings.get("portal", {})
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            self.logger.error("could not load settings: {}".format(e))
            raise
        except Exception as e:
            self.logger.error("could not load settings: {}".format(e))
            raise

    def run(self, path, **kwargs):
        self.logger.info("processing {} for registration with dart".format(path))
        body = None

        try:
            if (path == "-"):
                body = yaml.load(sys.stdin.read(), Loader=yaml.SafeLoader)
            else:
                with open(path, "r") as f:
                    body = yaml.load(f.read(), Loader=yaml.SafeLoader)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            self.logger.error("could not load {}: {}".format(path, e))
            return
        except Exception:
            self.logger.error(traceback.format_exc())
            raise

        if (body is None):
            self.logger.error("found no valid configurations in {}".format(path))
            return

        # send it to the dart api
        api = self.settings.get("api", {}).get("dart")
        if (api is None):
            self.logger.error("found no configuration to connect to the API")
            return
        if (not isinstance(api, dict)):
            self.logger.error("found invalid API configuration")
            return
        if (not api.get("url")):
            self.logger.error("found invalid API configuration")
            return

        try:
            response = requests.post(
                "{}/portal/v1/register".format(api["url"]),
                cert=api.get("key"),
                verify=api.get("ca"),
                data=json.dumps(body),
                timeout=60,
            )
            data = response.json()

            # try to print something helpful
            if (response.status_code != 200):
                self.logger.error("Received error back from dart: {}".format(data.get("message") or "Unknown error."))
                return

            # then raise the exception to abort the system
            response.raise_for_status()
        except Exception as e:
            self.logger.error("could not write process registration: {}".format(e))
