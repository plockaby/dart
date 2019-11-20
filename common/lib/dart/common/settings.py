import logging
from collections.abc import Mapping
from dart.common.singleton import Singleton
import pkg_resources
import yaml


class SettingsManager(Mapping, metaclass=Singleton):
    def __init__(self, lazy=False):
        self.logger = logging.getLogger(__name__)

        if (not lazy):
            self.init_app(None)

    # this is used by flask
    def init_app(self, app):
        try:
            # get the data out of the file
            data = pkg_resources.resource_string("dart", "settings/settings.yaml").decode("utf-8", "backslashreplace")

            # convert the settings data from yaml to a python data structure
            # this will definitely throw exceptions if the settings file is invalid
            settings = yaml.load(data, Loader=yaml.SafeLoader)

            # flatten the settings for easier access
            self.settings = self.flatten(settings)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            self.logger.error("could not load settings: {}".format(e))
            raise
        except Exception as e:
            self.logger.error("could not load settings: {}".format(e))
            raise

    def flatten(self, settings):
        result = {}

        def recurse(t, parent_key=""):
            if isinstance(t, dict):
                for k, v in t.items():
                    recurse(v, "{}.{}".format(parent_key, k) if parent_key else k)
            else:
                result[parent_key] = t

        recurse(settings)
        return result

    def __getitem__(self, key):
        return self.settings[key]

    def __iter__(self):
        return iter(self.settings)

    def __len__(self):
        return len(self.settings)
