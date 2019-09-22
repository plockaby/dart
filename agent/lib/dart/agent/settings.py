import logging
from collections.abc import Mapping
from dart.common.singleton import Singleton
import pkg_resources
import yaml


class SettingsManager(Mapping, metaclass=Singleton):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        try:
            # get the data out of the file
            data = pkg_resources.resource_string("dart", "settings/settings.yaml").decode("utf-8", "backslashreplace")

            # convert the settings data from yaml to a python data structure
            # this will definitely throw exceptions if the settings file is invalid
            settings = yaml.load(data, Loader=yaml.SafeLoader)

            # now pull out the "agent" settings. our code should set good defaults.
            self.settings = settings.get("agent", {})
        except Exception as e:
            self.logger.error("could not load settings: {}".format(e))
            raise

    def __getitem__(self, key):
        return self.settings[key]

    def __iter__(self):
        return iter(self.settings)

    def __len__(self):
        return len(self.settings)
