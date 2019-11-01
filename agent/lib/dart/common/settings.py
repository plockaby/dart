from collections.abc import Mapping
import pkg_resources
import yaml


class SettingsManager(Mapping):
    def __init__(self, app=None, **kwargs):
        if (app is not None):
            self.init_app(app, **kwargs)
        else:
            self.app = None

    def init_app(self, app, key):
        # get the data out of the file
        data = pkg_resources.resource_string("dart", "settings/settings.yaml").decode("utf-8", "backslashreplace")

        # convert the settings data from yaml to a python data structure
        # this will definitely throw exceptions if the settings file is invalid
        settings = yaml.load(data, Loader=yaml.SafeLoader)

        # now pull out the settings that we're looking for
        self.settings = settings.get(key, {})

    def __getitem__(self, key):
        return self.settings[key]

    def __iter__(self):
        return iter(self.settings)

    def __len__(self):
        return len(self.settings)
