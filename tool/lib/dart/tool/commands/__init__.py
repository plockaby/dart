import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib.parse
from dart.common.settings import SettingsManager


class BaseCommand(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # settings are only needed here, to connect to the api
        settings_manager = SettingsManager()

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
        self.dart_api.cert = settings_manager.get("tool.api.dart.key")
        self.dart_api.verify = settings_manager.get("tool.api.dart.ca")
        self.dart_api.mount("https://", HTTPAdapter(pool_block=True, max_retries=retry))
        self.dart_api_url = settings_manager.get("tool.api.dart.url")

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
