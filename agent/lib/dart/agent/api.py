import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from dart.common.settings import SettingsManager


# this is a collection of settings for accessing apis
__settings = SettingsManager()

# this sets a custom retry policy. we will retry a few times in case we
# hit a server that is transitioning into offline state. with 6 retries
# and a backoff factor of 1.0 this means that we will wait this many
# seconds after each failure before trying again: 0, 1, 2, 4, 8, 16.
# see here for more documentation:
#   https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#module-urllib3.util.retry
__retry = Retry(
    total=6,
    backoff_factor=1.0,  # retry after 0, 1, 2, 4, 8, 16 seconds
    status_forcelist=(500, 502, 503, 504),  # always retry on these response codes
    method_whitelist=False,  # retry for all request types
)

# block until we get a connection to the remote server
__adapter = HTTPAdapter(pool_block=True, max_retries=__retry)

# where can we get the DartAPI
DART_API_URL = __settings.get("agent.api.dart.url")

# the urls for the CorkAPI
CORK_API_URL = __settings.get("agent.api.cork.url")

# connection pool for the DartAPI
dart = requests.Session()
dart.cert = __settings.get("agent.api.dart.key")
dart.verify = __settings.get("agent.api.dart.ca")
dart.mount("https://", __adapter)

# connection pool for the CorkAPI
cork = requests.Session()
cork.cert = __settings.get("agent.api.cork.key")
cork.verify = __settings.get("agent.api.cork.ca")
cork.mount("https://", __adapter)
