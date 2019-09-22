import logging
from collections.abc import Mapping
from dart.common.singleton import Singleton
import dart.agent.api
from .settings import SettingsManager
from threading import RLock
import urllib.parse
import socket
import pwd
import grp
import os


class ConfigurationsWriter(metaclass=Singleton):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # we only want one person writing configurations at a time
        self.lock = RLock()

        # we need to load configurations for our host name
        self.fqdn = socket.getfqdn()

        # load settings from the settings manager
        self.settings = SettingsManager().get("configuration", {})

        # this is where we will keep configurations
        configuration_path = self.settings.get("path", "/run/dart")
        self.logger.debug("writing configuration files to {}".format(configuration_path))

        # these are the actual configuration files for the tools. these should
        # be found under the configuration path.
        self.supervisor_configuration_path = os.path.join(configuration_path, "supervisor.conf")

        # try to ensure that our configurations can exist somewhere. this will
        # raise an exception if the directory can't be created. that's ok, let
        # it bubble up to the caller.
        os.makedirs(configuration_path, mode=0o755, exist_ok=True)

    def write(self):
        with self.lock:
            # drop permissions if we need to or can
            self._drop_permissions()

            # fetch assignments and configurations from DartAPI. then sort them
            # by name so that the configuration files can be read by humans.
            assignments = self._get_assignments()
            assignments.sort(key=lambda x: x["name"])

            # now write the configurations to disk
            self._load_dart_configurations(assignments)
            self._write_supervisor_configurations(assignments)

    def _drop_permissions(self):
        # drop permissions if we're root
        starting_uid = os.getuid()
        starting_gid = os.getgid()

        # if we're not root then we don't (can't) drop permissions
        if (starting_uid != 0):
            return

        # figure out where we are and where we are going
        starting_user = pwd.getpwuid(starting_uid)[0]
        starting_group = grp.getgrgid(starting_gid)[0]
        desired_user = self.settings.get("user")
        desired_group = self.settings.get("group")

        # try dropping group
        if (desired_group is not None):
            try:
                self.logger.info("dropping group from {} to {}".format(starting_group, desired_group))
                desired_gid = grp.getgrnam(desired_group)[2]
                os.setgid(desired_gid)
            except KeyError as e:
                self.logger.error("could not find group {}: {}".format(desired_group, e))
                raise
            except PermissionError as e:
                self.logger.error("could not change to group {}:{}: {}".format(desired_group, e))
                raise

        # then try dropping user
        # this order is important
        if (desired_user is not None):
            try:
                self.logger.info("dropping user from {} to {}".format(starting_user, desired_user))
                desired_uid = pwd.getpwnam(desired_user)[2]
                os.setuid(desired_uid)
            except KeyError as e:
                self.logger.error("could not find user {}: {}".format(desired_user, e))
                raise
            except PermissionError as e:
                self.logger.error("could not change to user {}: {}".format(desired_user, e))
                raise

    def _get_assignments(self):
        url = "{}/agent/v1/assigned/{}".format(dart.agent.api.DART_API_URL, urllib.parse.quote(self.fqdn))
        self.logger.debug("fetching assigned processes from '{}'".format(url))
        response = dart.agent.api.dart.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def _load_dart_configurations(self, assignments):
        # initialize configuration data structure. in all cases the key to the
        # empty dicts is the name of the process.
        data = {
            "schedule": {},
            "monitor": {
                "state": {},
                "daemon": {},
                "keepalive": {},
                "log": {"stdout": {}, "stderr": {}},
            }
        }

        for assignment in assignments:
            name = assignment["name"]  # what is the name of the process

            # disabled processes are not monitored and are not scheduled
            if (assignment["disabled"]):
                continue

            # only write the schedule if the process has one
            if (assignment["schedule"]):
                data["schedule"][name] = assignment["schedule"]

            monitors = assignment["monitors"]
            if (monitors.get("state") is not None):
                data["monitor"]["state"][name] = monitors["state"]
            if (monitors.get("daemon") is not None):
                data["monitor"]["daemon"][name] = monitors["daemon"]
            if (monitors.get("keepalive") is not None):
                data["monitor"]["keepalive"][name] = monitors["keepalive"]
            if (monitors.get("log") is not None):
                data["monitor"]["log"]["stdout"][name] = monitors["log"]["stdout"]
                data["monitor"]["log"]["stderr"][name] = monitors["log"]["stderr"]

        # get the configurations manager and reload the configuration
        ConfigurationsManager().reload(data)

    def _write_supervisor_configurations(self, assignments):
        # take the configurations and write them to a file that supervisord
        # will read. we're going to write a temporary file and then replace the
        # existing file with the temporary file.
        temporary_path = "{}.tmp".format(self.supervisor_configuration_path)
        self.logger.debug("writing new supervisor configuration file: {}".format(temporary_path))
        with open(temporary_path, "w") as f:
            for assignment in assignments:
                print("[{}:{}]".format(assignment["type"], assignment["name"]), file=f)
                print(assignment["configuration"], file=f)
                print("", file=f)

        # move temp file into place. the os.replace function is atomic so
        # we can be sure that nothing will read an empty file while we move
        # the new one into place
        self.logger.debug("moving {} to {}".format(temporary_path, self.supervisor_configuration_path))
        os.replace(temporary_path, self.supervisor_configuration_path)


class ConfigurationsManager(Mapping, metaclass=Singleton):
    def __init__(self):
        # control access to the data structure so that we can reload it
        self.lock = RLock()

        # initialize our backing dict
        with self.lock:
            self.configurations = {}

    def reload(self, configurations):
        with self.lock:
            self.configurations.clear()
            self.configurations.update(configurations)

    def __getitem__(self, key):
        with self.lock:
            return self.configurations[key]

    def __iter__(self):
        with self.lock:
            return iter(self.configurations)

    def __len__(self):
        with self.lock:
            return len(self.configurations)
