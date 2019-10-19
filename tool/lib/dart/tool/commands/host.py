from . import BaseCommand
import dart.common
from termcolor import colored
from datetime import datetime
import urllib.parse
import traceback


class HostsCommand(BaseCommand):
    def run(self, **kwargs):
        try:
            print(colored("{:<80}".format("Hosts"), "grey", "on_white", attrs=["bold"]))

            url = "{}/tool/v1/hosts".format(self.dart_api_url)
            response = self.dart_api.get(url, timeout=10)
            response.raise_for_status()
            hosts = response.json()

            # consistently tell our user what the current time is
            now = datetime.now()

            # get the max host name size
            width = 0
            for host in hosts:
                if (len(host["fqdn"]) > width):
                    width = len(host["fqdn"])

            for host in hosts:
                print("{{:<{}}}".format(width + 3).format(host["fqdn"]), end="")

                parts = []
                parts.append(colored("{:>2} total".format(host["total"]), "cyan", attrs=["bold"]))
                parts.append(colored("{:>2} running".format(host["running"]), "green", attrs=["bold"]))
                parts.append(colored("{:>2} stopped".format(host["stopped"]), "yellow", attrs=["bold"]))

                if (host["failed"] > 0):
                    parts.append(colored("{:>2} failed".format(host["failed"]), "red", attrs=["bold"]))

                if (host["pending"] > 0):
                    parts.append(colored("{:>2} pending".format(host["pending"]), "red", attrs=["bold"]))

                if (host["disabled"] > 0):
                    parts.append(colored("{:>2} disabled".format(host["disabled"]), "red", attrs=["bold"]))

                # this is when we last polled this host
                last_polled = host["polled"]

                if (last_polled is None):
                    parts.append(colored("never polled", "red", attrs=["bold"]))
                else:
                    # show a message if the host hasn't been polled in more than
                    # four hours. but we need to be in the right timezone first.
                    last_polled_timestamp = datetime.strptime(last_polled, "%Y-%m-%d %H:%M:%S").timestamp()
                    if (now.timestamp() - last_polled_timestamp > (60 * 60 * 4)):
                        parts.append(colored("{} hours old".format(round(((now.timestamp() - last_polled_timestamp) / 3600), 1)), "red", attrs=["bold"]))

                print(", ".join(parts))

            return 0
        except Exception as e:
            print("{} Could not get the list of hosts: {}".format(colored("FAILURE!", "red", attrs=["bold"]), e))
            self.logger.debug(traceback.format_exc())
            return 1


class HostCommand(BaseCommand):
    def run(self, fqdn, **kwargs):
        try:
            # consistently tell our user what the current time is
            now = datetime.now()

            url = "{}/tool/v1/hosts/{}".format(self.dart_api_url, urllib.parse.quote(fqdn))
            response = self.dart_api.get(url, timeout=10)

            # if we get a 404 then give something informative
            if (response.status_code == 404):
                print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
                return 1

            # for everything else just raise an exception
            response.raise_for_status()

            # then convert the json data into a python data structure
            host = response.json()

            print(colored("{:<80}".format("Host Details - {}".format(fqdn)), "grey", "on_white", attrs=["bold"]))
            print("         Host: {}".format(fqdn))

            if (host["polled"]):
                print("       Polled: {}".format(host["polled"]))
            else:
                print("       Polled: unknown")

            if (host["booted"]):
                print("       Booted: {}".format(host["booted"]))
            else:
                print("       Booted: unknown")

            print("       Kernel: {}".format(host["kernel"] if host["kernel"] is not None else "unknown"))
            print("")

            active = {}
            pending = {}
            assigned = {}

            # we need better versions of the active/pending/assigned lists that
            # will let us key into the lists by process name.
            for process in host["active"]:
                active[process["name"]] = process
            for process in host["pending"]:
                pending[process["name"]] = process
            for process in host["assignments"]:
                assigned[process["name"]] = process

            # now show active configurations
            print(colored("{:<80}".format("Active Configurations"), "grey", "on_white", attrs=["bold"]))
            if (len(active)):
                process_name_width = 0
                description_width = 0
                for process_name, details in active.items():
                    if (len(process_name) > process_name_width):
                        process_name_width = len(process_name)
                    if (len(details["description"]) > description_width):
                        description_width = len(details["description"])

                for process_name, details in sorted(active.items()):
                    # the name of the process
                    print(" {{:<{}}}   ".format(process_name_width).format(process_name), end="")

                    # show a different color for the state depending on what it is
                    state = details["state"]
                    if (state == "RUNNING"):
                        state = colored(state, "green")
                    if (state in ["STARTING", "STOPPED", "STOPPING", "EXITED"]):
                        state = colored(state, "yellow")
                    if (state in ["BACKOFF", "FATAL", "UNKNOWN"]):
                        state = colored(state, "red", attrs=["bold"])
                    print("{}{}".format(state, " " * (10 - len(details["state"]))), end="")

                    # the description that supervisord gives it
                    print("{{:<{}}}   ".format(description_width).format(details["description"]), end="")

                    # this is the trailing notes
                    notes = []

                    # if this isn't configured we should know
                    if (process_name not in dart.common.PROCESSES_TO_IGNORE and process_name not in assigned):
                        notes.append(colored("not configured", "red", attrs=["bold"]))

                    # if the process isn't running when it should be, let's know that, too
                    if (process_name in assigned and assigned[process_name]["daemon"]):
                        if (details["state"] != "RUNNING"):
                            notes.append(colored("daemon not running", "red", attrs=["bold"]))
                        else:
                            notes.append(colored("daemon online", "cyan"))

                    # if the process is scheduled to start, let's display the next time it starts
                    if (process_name in assigned and assigned[process_name]["schedule"]):
                        schedule = assigned[process_name]["schedule"]
                        if (schedule):
                            starts = assigned[process_name]["starts"]
                            if (starts):
                                starts = datetime.strptime(starts, "%Y-%m-%d %H:%M:%S")
                                delay = int(starts.timestamp()) - int(now.timestamp())
                                if (delay > 86400):
                                    starts = "{} days".format(round(delay / 60 / 60 / 24, 1))
                                elif (delay > 3600):
                                    starts = "{} hours".format(round(delay / 60 / 60, 1))
                                elif (delay > 60):
                                    starts = "{} minutes".format(int(delay / 60))
                                else:
                                    starts = "{} seconds".format(delay)

                                notes.append(colored("starts in {}".format(starts), "cyan"))
                            else:
                                notes.append(colored("invalid schedule", "red", attrs=["bold"]))

                    if (details["error"]):
                        notes.append(colored(details["error"], "red", attrs=["bold"]))

                    print(", ".join(notes))
            else:
                print(" No active configurations found on '{}'".format(fqdn))
            print("")

            # now show pending configurations
            print(colored("{:<80}".format("Pending Configurations"), "grey", "on_white", attrs=["bold"]))
            if (len(pending)):
                process_name_width = 0
                for process_name in pending:
                    if (len(process_name) > process_name_width):
                        process_name_width = len(process_name)

                state_width = 0
                for process_name in pending:
                    if (len(pending[process_name]["state"]) > state_width):
                        state_width = len(pending[process_name]["state"])

                for process_name, details in sorted(pending.items()):
                    print(" {{:<{}}}  ".format(process_name_width).format(process_name), end="")
                    state = colored(details["state"].upper(), "red", attrs=["bold"])
                    print(" {}{}  ".format(state, " " * (10 - len(details["state"]))), end="")
                    if (details["disabled"]):
                        print(" {}".format(colored("DISABLED", "red", attrs=["bold"])), end="")
                    else:
                        print(" {}".format(colored("ENABLED", "green", attrs=["bold"])), end="")
                    print("")
            else:
                print(" No pending configuration changes found on '{}'".format(fqdn))
            print("")

            # finally show what processes are assigned to this host and their schedule
            print(colored("{:<80}".format("Assigned Configurations"), "grey", "on_white", attrs=["bold"]))
            if (len(assigned)):
                # the maximum width of the process name and environment
                process_name_width = 0
                environment_width = 0
                type_width = 0
                for process_name, details in assigned.items():
                    if (len(process_name) > process_name_width):
                        process_name_width = len(process_name)
                    if (len(details["environment"]) > environment_width):
                        environment_width = len(details["environment"])
                    if (len(details["type"])):
                        type_width = len(details["type"])

                for process_name, details in sorted(assigned.items()):
                    # the name of the process
                    print(" {{:<{}}}   ".format(process_name_width).format(process_name), end="")

                    # the process's environment
                    print("{{:<{}}}   ".format(environment_width).format(details["environment"]), end="")

                    # the type of program
                    print("{{:<{}}}   ".format(type_width).format(details["type"]), end="")

                    # is the process disabled?
                    if (details["disabled"]):
                        print(colored("DISABLED", "red", attrs=["bold"]), end="")
                    else:
                        print("        ", end="")  # spacing for DISABLED

                    # the process's schedule
                    if (details["schedule"]):
                        print("   {}".format(details["schedule"]), end="")

                    print("")
            else:
                print(" No processes are assigned to '{}'".format(fqdn))
            print("")

            return 0
        except Exception as e:
            print("{} Could not get the host: {}".format(colored("FAILURE!", "red", attrs=["bold"]), e))
            self.logger.debug(traceback.format_exc())
            return 1
