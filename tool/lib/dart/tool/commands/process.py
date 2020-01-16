from . import BaseCommand
import dart.common
from termcolor import colored
from datetime import datetime
import urllib.parse
import traceback


class ProcessesCommand(BaseCommand):
    def run(self, **kwargs):
        try:
            print(colored("{:<80}".format("Processes"), "grey", "on_white", attrs=["bold"]))

            url = "{}/tool/v1/processes".format(self.dart_api_url)
            response = self.dart_api.get(url, timeout=10)
            response.raise_for_status()
            processes = response.json()

            # get the max process name size
            width = 0
            for process in processes:
                if (len(process["name"]) > width):
                    width = len(process["name"])

            for process in processes:
                # the name of the process
                print("{{:<{}}}".format(width + 3).format(process["name"]), end="")

                # going to append a bunch of stuff after the process name
                parts = []

                if (process["name"] in dart.common.PROCESSES_TO_IGNORE):
                    # these are automatically assigned outside of the database
                    parts.append(colored("{:>2} assigned".format(process["active"]), "cyan", attrs=["bold"]))
                else:
                    # everything else must be manually assigned
                    parts.append(colored("{:>2} assigned".format(process["assigned"]), "cyan", attrs=["bold"]))

                # how many are actually configured and active in supervisor on hosts
                parts.append(colored("{:>2} active".format(process["active"]), "green", attrs=["bold"]))

                if (process["disabled"] > 0):
                    parts.append(colored("{:>2} disabled".format(process["disabled"]), "red", attrs=["bold"]))

                if (process["pending"] > 0):
                    parts.append(colored("{:>2} pending".format(process["pending"]), "red", attrs=["bold"]))

                if (process["failed"] > 0):
                    parts.append(colored("{:>2} failed".format(process["failed"]), "red", attrs=["bold"]))

                if (process["name"] not in dart.common.PROCESSES_TO_IGNORE):
                    if (process["assigned"] == 0):
                        parts.append(colored("not assigned", "red", attrs=["bold"]))

                    if (process["configured"] == 0):
                        parts.append(colored("active but not configured", "red", attrs=["bold"]))

                    if (len(set(process["active_hosts"]).difference(process["assigned_hosts"]))):
                        parts.append(colored("active on hosts not assigned", "red", attrs=["bold"]))

                    if (len(set(process["pending_hosts"]).difference(process["assigned_hosts"]))):
                        parts.append(colored("pending on hosts not assigned", "red", attrs=["bold"]))

                print(", ".join(parts))

            return 0
        except Exception as e:
            print("{} Could not get the list of processes: {}".format(colored("FAILURE!", "red", attrs=["bold"]), e))
            self.logger.debug(traceback.format_exc())
            return 1


class ProcessCommand(BaseCommand):
    def run(self, name, **kwargs):
        try:
            # consistently tell our user what the current time is
            now = datetime.now()

            url = "{}/tool/v1/processes/{}".format(self.dart_api_url, urllib.parse.quote(name))
            response = self.dart_api.get(url, timeout=10)

            # if we get a 404 then give something informative
            if (response.status_code == 404):
                print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), name))
                return 1

            # for everything else just raise an exception
            response.raise_for_status()

            # then convert the json data into a python data structure
            process = response.json()

            active = {}
            pending = {}
            assigned = {}

            # we need better versions of the active/pending/assigned lists that
            # will let us key into the lists by process name.
            for host in process["active"]:
                active[host["fqdn"]] = host
            for host in process["pending"]:
                pending[host["fqdn"]] = host
            for host in process["assignments"]:
                assigned[host["fqdn"]] = host

            print(colored("{:<80}".format("Configuration - {}".format(name)), "grey", "on_white", attrs=["bold"]))
            for environment in process["environments"]:
                print(" {}".format(colored(environment["name"], "cyan", attrs=["bold"])))
                process_type = environment["type"]
                configuration = environment["configuration"]

                print("   Type:")
                if (process_type is not None):
                    print("      {}".format(process_type))
                else:
                    print("      No type defined.")
                print("")

                print("   Configuration:")
                if (configuration is not None):
                    for line in configuration.strip().split("\n"):
                        print("      {}".format(line))
                else:
                    print("      No configuration defined.")
                print("")

                schedule = environment["schedule"]
                print("   Schedule:")
                if (schedule is not None):
                    print("      {}".format(schedule))
                else:
                    print("      No schedule defined.")
                print("")

            # where is it actively running
            print(colored("{:<80}".format("Active Configurations - {}".format(name)), "grey", "on_white", attrs=["bold"]))
            if (len(process["active"])):
                # the maximum width of the fqdn and description
                fqdn_width = 0
                description_width = 0
                for active in process["active"]:
                    if (len(active["fqdn"]) > fqdn_width):
                        fqdn_width = len(active["fqdn"])
                    if (len(active["description"]) > description_width):
                        description_width = len(active["description"])

                for active in process["active"]:
                    # the name of the host
                    print(" {{:<{}}}   ".format(fqdn_width).format(active["fqdn"]), end="")

                    # show a different color for the state depending on what it is
                    state = active["state"]
                    if (state == "RUNNING"):
                        state = colored(state, "green")
                    if (state in ["STARTING", "STOPPED", "STOPPING", "EXITED"]):
                        state = colored(state, "yellow")
                    if (state in ["BACKOFF", "FATAL", "UNKNOWN"]):
                        state = colored(state, "red", attrs=["bold"])
                    print("{}{}".format(state, " " * (10 - len(active["state"]))), end="")

                    # the description that supervisord gives it
                    print("{{:<{}}}   ".format(description_width).format(active["description"]), end="")

                    # this is the trailing notes
                    notes = []

                    # if the process isn't running when it should be, let's know that, too
                    if (active["fqdn"] in assigned and active["daemon"]):
                        if (active["state"] != "RUNNING"):
                            notes.append(colored("daemon not running", "red", attrs=["bold"]))
                        else:
                            notes.append(colored("daemon online", "cyan"))

                    # if the process is scheduled to start, let's display the next time it starts
                    if (active["fqdn"] in assigned and assigned[active["fqdn"]]["schedule"]):
                        schedule = assigned[active["fqdn"]]["schedule"]
                        if (schedule):
                            starts = assigned[active["fqdn"]]["starts"]
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

                    if (active["fqdn"] not in assigned and name not in dart.common.PROCESSES_TO_IGNORE):
                        notes.append(colored("not assigned", "red", attrs=["bold"]))

                    if (active["error"]):
                        notes.append(colored(active["error"], "red", attrs=["bold"]))

                    print(", ".join(notes))
            else:
                print(" No hosts have active configurations for the process '{}'".format(name))
            print("")

            # where are pending configuration changes awaiting application
            print(colored("{:<80}".format("Pending Configurations - {}".format(name)), "grey", "on_white", attrs=["bold"]))
            if (len(process["pending"])):
                fqdn_width = 0
                state_width = 0
                for pending in process["pending"]:
                    if (len(pending["fqdn"]) > fqdn_width):
                        fqdn_width = len(pending["fqdn"])
                    if (len(pending["state"]) > state_width):
                        state_width = len(pending["state"])

                for pending in process["pending"]:
                    print(" {{:<{}}}  ".format(fqdn_width).format(pending["fqdn"]), end="")
                    state = colored(pending["state"].upper(), "red", attrs=["bold"])
                    print(" {}{}  ".format(state, " " * (10 - len(pending["state"]))), end="")
                    if (pending["disabled"]):
                        print(" {}   ".format(colored("DISABLED", "red", attrs=["bold"])), end="")
                    else:
                        print(" {}    ".format(colored("ENABLED", "green", attrs=["bold"])), end="")

                    # if the process is is not assigned to this host but still has
                    # a pending change then note that next to the pending record.
                    if (pending["fqdn"] not in assigned and name not in dart.common.PROCESSES_TO_IGNORE):
                        print(" {}".format(colored("NOT ASSIGNED", "red", attrs=["bold"])), end="")

                    # ok now we can print a newline
                    print("")
            else:
                print(" No hosts have pending configuration changes for the process '{}'".format(name))
            print("")

            # to what hosts has it been assigned
            print(colored("{:<80}".format("Assignments - {}".format(name)), "grey", "on_white", attrs=["bold"]))
            if (len(process["assignments"])):
                # the maximum width of the fqdn and environment
                fqdn_width = 0
                environment_width = 0
                process_type_width = 0
                for assigned in process["assignments"]:
                    if (len(assigned["fqdn"]) > fqdn_width):
                        fqdn_width = len(assigned["fqdn"])
                    if (len(assigned["environment"]) > environment_width):
                        environment_width = len(assigned["environment"])
                    if (len(assigned["type"]) > process_type_width):
                        process_type_width = len(assigned["type"])

                for assigned in process["assignments"]:
                    # the name of the host
                    print(" {{:<{}}}   ".format(fqdn_width).format(assigned["fqdn"]), end="")

                    # the host's environment
                    print("{{:<{}}}   ".format(environment_width).format(assigned["environment"]), end="")

                    # the host's program type
                    print("{{:<{}}}   ".format(process_type_width).format(assigned["type"]), end="")

                    # is the process disabled on this host?
                    if (assigned["disabled"]):
                        print(colored("DISABLED", "red", attrs=["bold"]), end="")
                    else:
                        print("        ", end="")  # spacing for DISABLED

                    # the process's schedule on this host
                    if (assigned["schedule"]):
                        print("   {}".format(assigned["schedule"]), end="")

                    print("")
            else:
                print(" No hosts have been assigned the process '{}'".format(name))
            print("")

            # the monitoring configurations
            print(colored("{:<80}".format("Monitoring Configurations - {}".format(name)), "grey", "on_white", attrs=["bold"]))

            for environment in process["environments"]:
                print(" {}".format(colored(environment["name"], "cyan", attrs=["bold"])))

                if (environment["name"] in process["monitoring"] and process["monitoring"][environment["name"]]["state"] is not None):
                    monitor = process["monitoring"][environment["name"]]["state"]
                    print("   State monitoring is {} at severity {},".format(colored("ENABLED", "green", attrs=["bold"]), monitor["severity"]), end="")

                    if (monitor.get("ci")):
                        if ("uuid" in monitor["ci"]):
                            print(" CI uuid {}".format(monitor["ci"]["uuid"]), end="")
                        elif ("name" in monitor["ci"]):
                            print(" CI '{}'".format(monitor["ci"]["name"]), end="")
                        else:
                            print(" {}".format(colored("invalid configuration item", "red", attrs=["bold"])), end="")
                    else:
                        print(" {}".format(colored("invalid configuration item", "red", attrs=["bold"])), end="")

                    print(".")
                else:
                    print("   State monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), name, environment["name"]))

                if (environment["name"] in process["monitoring"] and process["monitoring"][environment["name"]]["daemon"] is not None):
                    monitor = process["monitoring"][environment["name"]]["daemon"]
                    print("   Daemon monitoring is {} at severity {},".format(colored("ENABLED", "green", attrs=["bold"]), monitor["severity"]), end="")

                    if (monitor.get("ci")):
                        if ("uuid" in monitor["ci"]):
                            print(" CI uuid {}".format(monitor["ci"]["uuid"]), end="")
                        elif ("name" in monitor["ci"]):
                            print(" CI '{}'".format(monitor["ci"]["name"]), end="")
                        else:
                            print(" {}".format(colored("invalid configuration item", "red", attrs=["bold"])), end="")
                    else:
                        print(" {}".format(colored("invalid configuration item", "red", attrs=["bold"])), end="")

                    print(".")
                else:
                    print("   Daemon monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), name, environment["name"]))

                if (environment["name"] in process["monitoring"] and process["monitoring"][environment["name"]]["heartbeat"] is not None):
                    monitor = process["monitoring"][environment["name"]]["heartbeat"]
                    print("   Heartbeat monitoring is {} at severity {}, {} minute timeout,".format(colored("ENABLED", "green", attrs=["bold"]), monitor["severity"], monitor["timeout"]), end="")

                    if (monitor.get("ci")):
                        if ("uuid" in monitor["ci"]):
                            print(" CI uuid {}".format(monitor["ci"]["uuid"]), end="")
                        elif ("name" in monitor["ci"]):
                            print(" CI '{}'".format(monitor["ci"]["name"]), end="")
                        else:
                            print(" {}".format(colored("invalid configuration item", "red", attrs=["bold"])), end="")
                    else:
                        print(" {}".format(colored("invalid configuration item", "red", attrs=["bold"])), end="")

                    print(".")
                else:
                    print("   Heartbeat monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), name, environment["name"]))

                if (environment["name"] in process["monitoring"] and process["monitoring"][environment["name"]]["log"] is not None and (len(process["monitoring"][environment["name"]]["log"]["stdout"]) or len(process["monitoring"][environment["name"]]["log"]["stderr"]))):
                    monitors = process["monitoring"][environment["name"]]["log"]
                    print("")
                    print("   Logs are matched in the order presented.")
                    for stream, monitor in sorted(monitors.items()):
                        for test in monitor:
                            print("   {}: {} matching '{}'".format(test["id"], test["stream"], test["regex"]))
                            print("      severity {}".format(test["severity"]))

                            if (test["ci"]):
                                if ("uuid" in test["ci"]):
                                    print("      CI uuid {}".format(test["ci"]["uuid"]))
                                elif ("name" in test["ci"]):
                                    print("      CI '{}'".format(test["ci"]["name"]))
                                else:
                                    print("      {}".format(colored("invalid configuration item", "red", attrs=["bold"])))

                            if (test["name"]):
                                print("      events created with name '{}'".format(test["name"]))
                            if (test["stop"]):
                                print("      matches to this regex will {} matching".format(colored("stop", "red", attrs=["bold"])))

                        # print a new line only if there were tests on this stream
                        if (len(monitor)):
                            print("")

                else:
                    print("   Log monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), name, environment["name"]))
                    print("")

            return 0
        except Exception as e:
            print("{} Could not get the process: {}".format(colored("FAILURE!", "red", attrs=["bold"]), e))
            self.logger.debug(traceback.format_exc())
            return 1
