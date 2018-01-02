from . import DataCommand
from termcolor import colored
import datetime
import dart.common
import dart.common.query


class ProcessesCommand(DataCommand):
    def run(self, **kwargs):
        print(colored("{:<80}".format("Processes"), "grey", "on_white", attrs=["bold"]))

        # this is details about all of the processes
        processes = dart.common.query.processes()

        # get the max process name size
        width = 0
        for process in processes:
            if (len(process) > width):
                width = len(process)

        for process, details in sorted(processes.items()):
            # the name of the process
            print("{{:<{}}}".format(width + 3).format(process), end="")

            # going to append a bunch of stuff after the process name
            parts = []

            if (process in dart.common.PROCESSES_TO_IGNORE):
                # these are automatically assigned outside of the database
                parts.append(colored("{:>2} assigned".format(details["active"]), "cyan", attrs=["bold"]))
            else:
                # everything else must be manually assigned
                parts.append(colored("{:>2} assigned".format(details["assigned"]), "cyan", attrs=["bold"]))

            # how many are actually configured and active in supervisor on hosts
            parts.append(colored("{:>2} active".format(details["active"]), "green", attrs=["bold"]))

            if (details["disabled"] > 0):
                parts.append(colored("{:>2} disabled".format(details["disabled"]), "red", attrs=["bold"]))

            if (details["pending"] > 0):
                parts.append(colored("{:>2} pending".format(details["pending"]), "red", attrs=["bold"]))

            if (details["failed"] > 0):
                parts.append(colored("{:>2} failed".format(details["failed"]), "red", attrs=["bold"]))

            if (process not in dart.common.PROCESSES_TO_IGNORE):
                if (details["assigned"] == 0):
                    parts.append(colored("not assigned", "red", attrs=["bold"]))

                if (details["configured"] == 0):
                    parts.append(colored("active but not configured", "red", attrs=["bold"]))

                if (len(details["active_hosts"].difference(details["assigned_hosts"]))):
                    parts.append(colored("active on hosts not assigned", "red", attrs=["bold"]))

                if (len(details["pending_hosts"].difference(details["assigned_hosts"]))):
                    parts.append(colored("pending on hosts not assigned", "red", attrs=["bold"]))

            print(", ".join(parts))

        return 0


class ProcessCommand(DataCommand):
    def run(self, process, **kwargs):
        # consistently tell our user what the current time is
        now = datetime.datetime.utcnow()

        if (not dart.common.query.is_valid_process(process)):
            print("{} No process named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), process))
            return 1

        # now get some generic information
        configurations = dart.common.query.process(process)

        # get configurations from cassandra
        active = dart.common.query.process_active(process)
        pending = dart.common.query.process_pending(process)
        assigned = dart.common.query.process_assigned(process)

        # get monitoring information from cassandra
        daemon_monitoring = dart.common.query.process_daemon_monitoring_configuration(process)
        state_monitoring = dart.common.query.process_state_monitoring_configuration(process)
        log_monitoring = dart.common.query.process_log_monitoring_configurations(process)

        # process details
        print(colored("{:<80}".format("Process Details - {}".format(process)), "grey", "on_white", attrs=["bold"]))
        print("  Process: {}".format(process))
        print("")

        print(colored("{:<80}".format("Configuration - {}".format(process)), "grey", "on_white", attrs=["bold"]))
        if (len(configurations)):
            for environment in sorted(configurations):
                print(" {}".format(colored(environment, "cyan", attrs=["bold"])))
                type = configurations[environment]["type"]
                configuration = configurations[environment]["configuration"]

                print("   Type:")
                if (type is not None):
                    print("      {}".format(type))
                else:
                    print("      No type defined.")
                print("")

                print("   Configuration:")
                if (configuration is not None):
                    for line in configuration.strip().split("\n"):
                        print("      {}".format(line))
                else:
                    print("      No configuration defined.")

                schedule = configurations[environment]["schedule"]
                print("   Schedule:")
                if (schedule is not None):
                    print("      {}".format(schedule))
                else:
                    print("      No schedule defined.")

                print("")
        else:
            print(" No configuration is defined for '{}'".format(process))
            print("")

        # to what hosts has it been assigned
        print(colored("{:<80}".format("Assignments - {}".format(process)), "grey", "on_white", attrs=["bold"]))
        if (len(assigned)):
            # the maximum width of the fqdn and environment
            fqdn_width = 0
            environment_width = 0
            type_width = 0
            for fqdn, details in assigned.items():
                if (len(fqdn) > fqdn_width):
                    fqdn_width = len(fqdn)
                if (len(details["environment"]) > environment_width):
                    environment_width = len(details["environment"])
                if (len(details["type"]) > type_width):
                    type_width = len(details["type"])

            for fqdn, details in sorted(assigned.items()):
                # the name of the host
                print(" {{:<{}}}   ".format(fqdn_width).format(fqdn), end="")

                # the host's environment
                print("{{:<{}}}   ".format(environment_width).format(details["environment"]), end="")

                # the host's program type
                print("{{:<{}}}   ".format(type_width).format(details["type"]), end="")

                # is the process disabled on this host?
                if (details["disabled"]):
                    print(colored("DISABLED", "red", attrs=["bold"]), end="")
                else:
                    print("        ", end="")  # spacing for DISABLED

                # the process's schedule on this host
                if (details["schedule"]):
                    print("   {}".format(details["schedule"]), end="")

                print("")
        else:
            print(" No hosts have been assigned the process '{}'".format(process))
        print("")

        # where is it actively running
        print(colored("{:<80}".format("Active Configurations - {}".format(process)), "grey", "on_white", attrs=["bold"]))
        if (len(active)):
            # the maximum width of the fqdn and description
            fqdn_width = 0
            description_width = 0
            for fqdn, details in active.items():
                if (len(fqdn) > fqdn_width):
                    fqdn_width = len(fqdn)
                if (len(details["description"]) > description_width):
                    description_width = len(details["description"])

            for fqdn, details in sorted(active.items()):
                # the name of the host
                print(" {{:<{}}}   ".format(fqdn_width).format(fqdn), end="")

                # show a different color for the status depending on what it is
                status = details["status"]
                if (status == "RUNNING"):
                    status = colored(status, "green")
                if (status in ["STARTING", "STOPPED", "STOPPING", "EXITED"]):
                    status = colored(status, "yellow")
                if (status in ["BACKOFF", "FATAL", "UNKNOWN"]):
                    status = colored(status, "red", attrs=["bold"])
                print("{}{}".format(status, " " * (10 - len(details["status"]))), end="")

                # the description that supervisord gives it
                print("{{:<{}}}   ".format(description_width).format(details["description"]), end="")

                # this is the trailing notes
                notes = []

                # if the process isn't running when it should be, let's know that, too
                if (fqdn in assigned and assigned[fqdn]["daemon"]):
                    if (details["status"] != "RUNNING"):
                        notes.append(colored("daemon not running", "red", attrs=["bold"]))
                    else:
                        notes.append(colored("daemon online", "cyan"))

                # if the process is scheduled to start, let's display the next time it starts
                if (fqdn in assigned and assigned[fqdn]["schedule"]):
                    schedule = assigned[fqdn]["schedule"]
                    if (schedule):
                        starts = assigned[fqdn]["starts"]
                        if (starts):
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

                if (fqdn not in assigned and process not in dart.common.PROCESSES_TO_IGNORE):
                    notes.append(colored("not assigned", "red", attrs=["bold"]))

                if (details["error"]):
                    notes.append(colored(details["error"], "red", attrs=["bold"]))

                print(", ".join(notes))
        else:
            print(" No hosts have active configurations for the process '{}'".format(process))
        print("")

        # where are pending configuration changes awaiting application
        print(colored("{:<80}".format("Pending Configurations - {}".format(process)), "grey", "on_white", attrs=["bold"]))
        if (len(pending)):
            fqdn_width = 0
            for fqdn in pending:
                if (len(fqdn) > fqdn_width):
                    fqdn_width = len(fqdn)

            status_width = 0
            for fqdn in pending:
                if (len(pending[fqdn]["status"]) > status_width):
                    status_width = len(pending[fqdn]["status"])

            for fqdn, details in sorted(pending.items()):
                print(" {{:<{}}}  ".format(fqdn_width).format(fqdn), end="")
                status = colored(details["status"].upper(), "red", attrs=["bold"])
                print(" {}{}  ".format(status, " " * (10 - len(details["status"]))), end="")
                if (details["disabled"]):
                    print(" {}   ".format(colored("DISABLED", "red", attrs=["bold"])), end="")
                else:
                    print(" {}    ".format(colored("ENABLED", "green", attrs=["bold"])), end="")

                # if the process is is not assigned to this host but still has
                # a pending change then note that next to the pending record.
                if (fqdn not in assigned and process not in dart.common.PROCESSES_TO_IGNORE):
                    print(" {}".format(colored("NOT ASSIGNED", "red", attrs=["bold"])), end="")

                # ok now we can print a newline
                print("")
        else:
            print(" No hosts have pending configuration changes for the process '{}'".format(process))
        print("")

        # the monitoring configurations
        print(colored("{:<80}".format("Monitoring Configurations - {}".format(process)), "grey", "on_white", attrs=["bold"]))

        if (len(configurations)):
            for environment in sorted(configurations):
                print(" {}".format(colored(environment, "cyan", attrs=["bold"])))

                if (environment in daemon_monitoring):
                    print("   Daemon monitoring is {} at severity {} for contact '{}'.".format(
                        colored("enabled", "green", attrs=["bold"]),
                        daemon_monitoring[environment]["severity"],
                        daemon_monitoring[environment]["contact"] or "DEFAULT",
                    ))
                else:
                    print("   Daemon monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), process, environment))

                if (environment in state_monitoring):
                    print("   State monitoring is {} at severity {} for contact '{}'.".format(
                        colored("enabled", "green", attrs=["bold"]),
                        state_monitoring[environment]["severity"],
                        state_monitoring[environment]["contact"] or "DEFAULT"
                    ))
                else:
                    print("   State monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), process, environment))

                if (len(log_monitoring.get(environment, []))):
                    print("")
                    print("   Logs are matched in the order presented.")
                    for monitor in log_monitoring[environment]:
                        print("   {}: {} matching '{}'".format(monitor["id"], monitor["stream"], monitor["regex"]))
                        print("      severity {} for contact '{}'.".format(monitor["severity"], monitor["contact"] or "DEFAULT"))
                        if (monitor["name"]):
                            print("      events created with name '{}'".format(monitor["name"]))
                        if (monitor["stop"]):
                            print("      matches to this regex will {} matching".format(colored("stop", "red", attrs=["bold"])))
                        print("")
                else:
                    print("   Log monitoring is {} for '{}' in {}.".format(colored("DISABLED", "red", attrs=["bold"]), process, environment))
        else:
            print(" No monitoring configurations are defined for '{}'".format(process))
            print("")

        return 0
