from . import DataCommand
from termcolor import colored
import dart.common.remote
import dart.common.query
import traceback


class RemoteCommand(DataCommand):
    def send(self, fqdn, action, process=None):
        # we aren't going to let anyone do anything to the dart agent
        if (process is not None and process == "dart-agent"):
            print("{} No changes may be made to dart-agent using this tool. Please use the host's supervisorctl command.".format(colored("FAILURE!", "red", attrs=["bold"])))
            return 1

        # validate that the host exists
        if (not dart.common.query.is_valid_host(fqdn)):
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1

        # validate that this process exists
        if (process is not None and not dart.common.query.is_valid_process(process)):
            print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process))
            return 1

        try:
            # actually send the message to the host
            dart.common.remote.command(fqdn, action, process)

            if (process):
                print("{} Message sent to {} to {} {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), fqdn, action, process))
            else:
                print("{} Message sent to {} to {}.".format(colored("SUCCESS!", "green", attrs=["bold"]), fqdn, action))
            return 0
        except Exception as e:
            if (process):
                print("{} Could not send message to {} to {} {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, action, process, e))
            else:
                print("{} Could not send message to {} to {}: {}".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn, action, e))
            self.logger.debug(traceback.format_exc())
            return 1


class StartCommand(RemoteCommand):
    def run(self, fqdn, process, **kwargs):
        return self.send(fqdn, "start", process)


class StopCommand(RemoteCommand):
    def run(self, fqdn, process, **kwargs):
        return self.send(fqdn, "stop", process)


class RestartCommand(RemoteCommand):
    def run(self, fqdn, process, **kwargs):
        return self.send(fqdn, "restart", process)


class UpdateCommand(RemoteCommand):
    def run(self, fqdn, process, **kwargs):
        return self.send(fqdn, "update", process)


class RereadCommand(RemoteCommand):
    def run(self, fqdn, **kwargs):
        return self.send(fqdn, "reread")


class RewriteCommand(RemoteCommand):
    def run(self, fqdn, **kwargs):
        return self.send(fqdn, "rewrite")
