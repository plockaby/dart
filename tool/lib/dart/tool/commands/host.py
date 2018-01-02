from . import DataCommand
from termcolor import colored
import datetime
import pytz.reference
import dart.common
import dart.common.query


class HostsCommand(DataCommand):
    def run(self, **kwargs):
        print(colored("{:<80}".format("Hosts"), "grey", "on_white", attrs=["bold"]))

        # consistently tell our user what the current time is
        now = datetime.datetime.utcnow()

        # this is details about all the hosts
        hosts = dart.common.query.hosts()

        # remove hosts that are not managed by dart
        hosts = {key: value for key, value in hosts.items()}

        # get the max host name size
        width = 0
        for fqdn in hosts:
            if (len(fqdn) > width):
                width = len(fqdn)

        for fqdn, details in sorted(hosts.items()):
            print("{{:<{}}}".format(width + 3).format(fqdn), end="")

            parts = []
            parts.append(colored("{:>2} total".format(details["total"]), "cyan", attrs=["bold"]))
            parts.append(colored("{:>2} running".format(details["running"]), "green", attrs=["bold"]))
            parts.append(colored("{:>2} stopped".format(details["stopped"]), "yellow", attrs=["bold"]))

            if (details["failed"] > 0):
                parts.append(colored("{:>2} failed".format(details["failed"]), "red", attrs=["bold"]))

            if (details["pending"] > 0):
                parts.append(colored("{:>2} pending".format(details["pending"]), "red", attrs=["bold"]))

            if (details["disabled"] > 0):
                parts.append(colored("{:>2} disabled".format(details["disabled"]), "red", attrs=["bold"]))

            # this is when we last checked this host
            last_checked = details["checked"]

            if (last_checked is None):
                parts.append(colored("never checked", "red", attrs=["bold"]))
            else:
                # show a message if the host hasn't been checked in more than
                # four hours. but we need to be in the right timezone first.
                last_checked_timestamp = last_checked.timestamp()
                if (now.timestamp() - last_checked_timestamp > (60 * 60 * 4)):
                    parts.append(colored("{} hours old".format(round(((now.timestamp() - last_checked_timestamp) / 3600), 1)), "red", attrs=["bold"]))

            print(", ".join(parts))

        return 0


class HostCommand(DataCommand):
    def run(self, fqdn, **kwargs):
        # consistently tell our user what the current time is
        now = datetime.datetime.utcnow()
        timezone = pytz.reference.LocalTimezone()

        if (not dart.common.query.is_valid_host(fqdn)):
            print("{} No host named {} is currently configured.".format(colored("FAILURE!", "red", attrs=["bold"]), fqdn))
            return 1

        # now get some generic information
        host = dart.common.query.host(fqdn)
        tags = dart.common.query.host_tags(fqdn)

        # get configurations from cassandra
        active = dart.common.query.host_active(fqdn)
        pending = dart.common.query.host_pending(fqdn)
        assigned = dart.common.query.host_assigned(fqdn)

        print(colored("{:<80}".format("Host Details - {}".format(fqdn)), "grey", "on_white", attrs=["bold"]))
        print("         Host: {}".format(fqdn))
        print("         Tags: {}".format(", ".join(sorted(tags)) if len(tags) else "None"))

        if (host["checked"]):
            checked = host["checked"].replace(tzinfo=datetime.timezone.utc).astimezone(tz=timezone)
            print("       Probed: {}".format(checked.strftime("%Y-%m-%d %H:%M:%S")))
        else:
            print("       Probed: unknown")

        if (host["system_started"]):
            system_started = host["system_started"].replace(tzinfo=datetime.timezone.utc).astimezone(tz=timezone)
            print("       Booted: {}".format(system_started.strftime("%Y-%m-%d %H:%M:%S")))
        else:
            print("       Booted: unknown")

        print("       Kernel: {}".format(host["kernel"]))
        print("")

        # now show active configurations
        print(colored("{:<80}".format("Active Configurations"), "grey", "on_white", attrs=["bold"]))
        if (len(active)):
            process_width = 0
            description_width = 0
            for process, details in active.items():
                if (len(process) > process_width):
                    process_width = len(process)
                if (len(details["description"] or "") > description_width):
                    description_width = len(details["description"] or "")

            for process, details in sorted(active.items()):
                # the name of the process
                print(" {{:<{}}}   ".format(process_width).format(process), end="")

                # show a different color for the status depending on what it is
                status = details["status"]
                if (status == "RUNNING"):
                    status = colored(status, "green")
                if (status in ["STARTING", "STOPPED", "STOPPING", "EXITED"]):
                    status = colored(status, "yellow")
                if (status in ["BACKOFF", "FATAL", "UNKNOWN"]):
                    status = colored(status, "red", attrs=["bold"])
                print("{}{}".format(status, " " * (10 - len(details["status"] or ""))), end="")

                # the description that supervisord gives it
                print("{{:<{}}}   ".format(description_width).format(details["description"] or ""), end="")

                # this is the trailing notes
                notes = []

                # if this isn't configured we should know
                if (process not in dart.common.PROCESSES_TO_IGNORE and process not in assigned):
                    notes.append(colored("not configured", "red", attrs=["bold"]))

                # if the process isn't running when it should be, let's know that, too
                if (process in assigned and assigned[process]["daemon"]):
                    if (details["status"] != "RUNNING"):
                        notes.append(colored("daemon not running", "red", attrs=["bold"]))
                    else:
                        notes.append(colored("daemon online", "cyan"))

                # if the process is scheduled to start, let's display the next time it starts
                if (process in assigned and assigned[process]["schedule"]):
                    schedule = assigned[process]["schedule"]
                    if (schedule):
                        starts = assigned[process]["starts"]
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

                if (details["error"]):
                    notes.append(colored(details["error"], "red", attrs=["bold"]))

                print(", ".join(notes))
        else:
            print(" No active configurations found on '{}'".format(fqdn))
        print("")

        # now show pending configurations
        print(colored("{:<80}".format("Pending Configurations"), "grey", "on_white", attrs=["bold"]))
        if (len(pending)):
            process_width = 0
            for process in pending:
                if (len(process) > process_width):
                    process_width = len(process)

            status_width = 0
            for process in pending:
                if (len(pending[process]["status"]) > status_width):
                    status_width = len(pending[process]["status"])

            for process, details in sorted(pending.items()):
                print(" {{:<{}}}  ".format(process_width).format(process), end="")
                status = colored(details["status"].upper(), "red", attrs=["bold"])
                print(" {}{}  ".format(status, " " * (10 - len(details["status"]))), end="")
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
            process_width = 0
            environment_width = 0
            type_width = 0
            for process, details in assigned.items():
                if (len(process) > process_width):
                    process_width = len(process)
                if (len(details["environment"]) > environment_width):
                    environment_width = len(details["environment"])
                if (len(details["type"])):
                    type_width = len(details["type"])

            for process, details in sorted(assigned.items()):
                # the name of the process
                print(" {{:<{}}}   ".format(process_width).format(process), end="")

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
