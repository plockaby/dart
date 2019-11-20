import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class APIManager:
    def __init__(self, app=None, **kwargs):
        if (app is not None):
            self.init_app(app, **kwargs)
        else:
            self.app = app

    def init_app(self, app):
        from .app import settings_manager

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
        self.dart_api.cert = settings_manager.get("portal.api.dart.key")
        self.dart_api.verify = settings_manager.get("portal.api.dart.ca")
        self.dart_api.mount("https://", HTTPAdapter(pool_block=True, max_retries=retry))
        self.dart_api_url = settings_manager.get("portal.api.dart.url")
