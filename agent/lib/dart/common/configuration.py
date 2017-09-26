import yaml
import pkg_resources


def load():
    # get the data out of the file
    data = pkg_resources.resource_string("dart", "configuration/settings.yaml").decode("utf-8", "backslashreplace")

    # convert the configuration data from yaml to a python data structure
    # this will definitely throw exceptions if the configuration file is invalid
    return yaml.load(data)
