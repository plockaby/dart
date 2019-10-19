import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib.parse
import pkg_resources
import yaml


class BaseCommand(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # try to load settings
        try:
            # get the data out of the file
            data = pkg_resources.resource_string("dart", "settings/settings.yaml").decode("utf-8", "backslashreplace")

            # convert the settings data from yaml to a python data structure
            # this will definitely throw exceptions if the settings file is invalid
            settings = yaml.load(data, Loader=yaml.SafeLoader)

            # now pull out the "tool" settings. our code should set good defaults.
            self.settings = settings.get("tool", {})
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            self.logger.error("could not load settings: {}".format(e))
            raise
        except Exception as e:
            self.logger.error("could not load settings: {}".format(e))
            raise

        # make sure that we have any api configuration
        configuration = self.settings.get("api", {}).get("dart")
        if (configuration is None):
            raise RuntimeError("found no configuration to connect to the API")
        if (not isinstance(configuration, dict)):
            raise RuntimeError("found invalid API configuration")
        if (not configuration.get("url")):
            raise RuntimeError("found invalid API configuration")

        # this sets a custom retry policy. we will retry a few times in case we
        # hit a server that is transitioning into offline state.
        retries = 3
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504),
        )

        # modify the number of retries that we will make. we will also block
        # until we get a connection to the remote server.
        self.dart_api = requests.Session()
        self.dart_api.cert = configuration.get("key")
        self.dart_api.verify = configuration.get("ca")
        self.dart_api.mount("https://", HTTPAdapter(pool_block=True, max_retries=retry))
        self.dart_api_url = configuration.get("url")

    def run(self, **kwargs):
        raise NotImplementedError("must be implemented in base class")

    def is_valid_host(self, fqdn):
        url = "{}/tool/v1/hosts/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
        response = self.dart_api.get(url, timeout=10)

        # see if the host is valid
        if (response.status_code == 200):
            return True
        elif (response.status_code == 404):
            return False

        # otherwise raise the exception
        response.raise_for_status()

    def is_valid_process(self, name):
        url = "{}/tool/v1/processes/{}".format(self.dart_api_url, urllib.parse.quote(name))
        response = self.dart_api.get(url, timeout=10)

        # see if the host is valid
        if (response.status_code == 200):
            return True
        elif (response.status_code == 404):
            return False

        # otherwise raise the exception
        response.raise_for_status()

    def is_valid_process_environment(self, name, environment):
        url = "{}/tool/v1/processes/{}/{}".format(self.dart_api_url, urllib.parse.quote(name), urllib.parse.quote(environment))
        response = self.dart_api.get(url, timeout=10)

        # see if the host is valid
        if (response.status_code == 200):
            return True
        elif (response.status_code == 404):
            return False

        # otherwise raise the exception
        response.raise_for_status()
