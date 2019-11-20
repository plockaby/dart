"""
This handler listens for TCP connections from the world. Those connections will
send us messages for actions to perform such as rereading configurations,
rewriting configurations, starting or stopping a process, or updating
supervisord. All connections must come in with a valid and authorized client
certificate.
"""

from . import BaseHandler
from dart.common.settings import SettingsManager
from dart.common.exceptions import CommandValidationException
from dart.common.supervisor import SupervisorClient
from threading import Thread
import socketserver
import ssl
import json
import xmlrpc.client
import traceback


class CoordinationHandler(BaseHandler):
    def __init__(self, reread_trigger, rewrite_trigger, supervisor_server_url, **kwargs):
        super().__init__(**kwargs)

        # configure settings by settingn some defaults
        self.settings = SettingsManager()
        self.settings["agent.coordination.address"] = self.settings.get("agent.coordination.address", "0.0.0.0")
        self.settings["agent.coordination.port"] = int(self.settings.get("agent.coordination.port", 3728))

        # where are we listening
        self.logger.info("{} handler listening for coordination events on {}:{}".format(
            self.name,
            self.settings["agent.coordination.address"],
            self.settings["agent.coordination.port"],
        ))

        # used by the actions
        self.reread_trigger = reread_trigger
        self.rewrite_trigger = rewrite_trigger
        self.supervisor_server_url = supervisor_server_url

        class RequestServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            # faster re-binding
            allow_reuse_address = True

            # make this bigger than five
            request_queue_size = 10

            # kick connections when we exit
            daemon_threads = True

            def __init__(subself, server_address, RequestHandlerClass, bind_and_activate=True):
                super().__init__(server_address, RequestHandlerClass, False)

                # create an ssl context using the given key/cert. the context
                # will require the client to present a certificate. we will
                # validate the client's certificate against the given ca.
                ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ctx.verify_mode = ssl.CERT_REQUIRED
                ctx.load_verify_locations(self.settings["agent.coordination.ca"])
                ctx.load_cert_chain(self.settings["agent.coordination.key"])

                # replace the socket with an ssl version of itself
                subself.socket = ctx.wrap_socket(subself.socket, server_side=True)

                # bind the socket and start the server
                if (bind_and_activate):
                    subself.server_bind()
                    subself.server_activate()

        class RequestHandler(socketserver.StreamRequestHandler):
            def handle(subself):
                self.logger.info("{} handler received connection from {}:{}".format(self.name, subself.client_address[0], subself.client_address[1]))

                try:
                    common_name = subself._get_certificate_common_name(subself.request.getpeercert())
                    if (common_name is None or common_name != self.settings["agent.coordination.name"]):
                        self.logger.warning("{} handler rejecting connection from {}".format(self.name, common_name))
                        return

                    # now we're going to listen to what they have to say
                    data = subself.rfile.readline().strip()
                    try:
                        subself._process_command(data)
                    except CommandValidationException as e:
                        self.logger.error("{} handler received invalid command: {}".format(self.name, e))

                        # first send it to the CorkAPI
                        self.events.put({
                            "data": {
                                "component": {"name": "agent:{}:command".format(self.name)},
                                "severity": 4,  # low priority
                                "message": "received invalid command\n\n{}".format(e),
                            }
                        })
                except BrokenPipeError:
                    self.logger.debug("{} handler broken pipe from {}:{}".format(self.name, subself.client_address[0], subself.client_address[1]))

            def _get_certificate_common_name(subself, cert):
                if (cert is None):
                    return None

                for sub in cert.get("subject", ()):
                    for key, value in sub:
                        if (key == "commonName"):
                            return value

            def _process_command(subself, data):
                # methods we implement on the supervisor xml-rpc api:
                # - startProcess(name, wait=False)  <- "wait" is True by default, we want false
                # - stopProcess(name, wait=False)  <- "wait" is True by default, we want false
                # - addProcessGroup(name)
                # - removeProcessGroup(name)

                # these are faux commands that we support
                # - restartProcess(name)  <- calls stop/start
                # - updateProcessGroup(name)  <- calls stop/add/remove

                # format is expected to look kind of like this:
                # {
                #     action="start/stop/add/remove/restart/update",  <- one of the commands above
                #     process="name",                                 <- the process against which to run the command
                # }

                # make sure that it is valid utf8 data and valid json
                try:
                    data = json.loads(data.decode("utf8"))
                except UnicodeDecodeError:
                    self.logger.warning("{} handler received non-UTF-8 data from {}:{}".format(self.name, subself.client_address[0], subself.client_address[1]))
                    raise CommandValidationException("Received non-UTF-8 data that could not be decoded. You must send data only in UTF-8.")
                except json.JSONDecodeError:
                    self.logger.warning("{} handler received non-JSON data from {}:{}".format(self.name, subself.client_address[0], subself.client_address[1]))
                    raise CommandValidationException("Received non-JSON data that could not be parsed. You must send only valid JSON data.")

                # some debugging
                self.logger.debug("{} handler received command '{}'".format(self.name, data))

                # make sure we have a valid action
                action = data.get("action")
                if (action is None or action.strip() == ""):
                    raise CommandValidationException("Received no action to take.")
                if (action not in ["start", "stop", "add", "remove", "restart", "update", "reread", "rewrite"]):
                    raise CommandValidationException("Received an invalid action to take.")

                if (action in ["reread", "rewrite"]):
                    if (action == "reread"):
                        self.logger.info("{} handler triggering a reread".format(self.name))
                        self.reread_trigger.set()
                    if (action == "rewrite"):
                        self.logger.info("{} handler triggering a rewrite".format(self.name))
                        self.rewrite_trigger.set()
                else:
                    # this is the thing we're going to do it to
                    process = data.get("process")
                    if (process is None or process.strip() == ""):
                        raise CommandValidationException("Received no process against which to take action.")

                    if (action == "start"):
                        subself.__start_process(process)
                    if (action == "stop"):
                        subself.__stop_process(process)
                    if (action == "restart"):
                        subself.__restart_process(process)
                    if (action == "add"):
                        subself.__add_process(process)
                    if (action == "remove"):
                        subself.__remove_process(process)
                    if (action == "update"):
                        subself.__update_process(process)

                    # after all commands we want to reread the system state
                    self.logger.info("{} handler triggering a reread".format(self.name))
                    self.reread_trigger.set()

            def __start_process(subself, process, wait=False):
                self.logger.info("{} handler starting process: {}".format(self.name, process))
                try:
                    client = SupervisorClient(self.supervisor_server_url)
                    client.connection.supervisor.startProcess(process, wait)
                except xmlrpc.client.Fault as e:
                    self.logger.warning("{} handler could not start process {}: {}".format(self.name, process, e.faultString))

            def __stop_process(subself, process, wait=False):
                self.logger.info("{} handler stopping process: {}".format(self.name, process))
                try:
                    client = SupervisorClient(self.supervisor_server_url)
                    client.connection.supervisor.stopProcess(process, wait)
                except xmlrpc.client.Fault as e:
                    self.logger.warning("{} handler could not stop process {}: {}".format(self.name, process, e.faultString))

            def __add_process(subself, process):
                self.logger.info("{} handler adding process: {}".format(self.name, process))
                try:
                    client = SupervisorClient(self.supervisor_server_url)
                    client.connection.supervisor.addProcessGroup(process)
                except xmlrpc.client.Fault as e:
                    self.logger.warning("{} handler could not add process {}: {}".format(self.name, process, e.faultString))

            def __remove_process(subself, process):
                self.logger.info("{} handler removing process: {}".format(self.name, process))
                try:
                    client = SupervisorClient(self.supervisor_server_url)
                    client.connection.supervisor.removeProcessGroup(process)
                except xmlrpc.client.Fault as e:
                    self.logger.warning("{} handler could not remove process {}: {}".format(self.name, process, e.faultString))

            def __restart_process(subself, process):
                subself.__stop_process(process, wait=True)
                subself.__start_process(process)

            def __update_process(subself, process):
                # we can't remove a process that is running
                subself.__stop_process(process, wait=True)

                # then actually remove it
                subself.__remove_process(process)

                # if a process is configured to automatically start then it will
                subself.__add_process(process)

        # this is the server. it handles the sockets. it passes requests to the
        # listener (the second argument). the server will run in its own thread
        # so that we can kill it when we need to
        self.server = RequestServer((self.settings["agent.coordination.address"], self.settings["agent.coordination.port"]), RequestHandler)

    @property
    def name(self):
        return "coordination"

    def start(self):
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the server to stop
        self.server.shutdown()

        # then wait for the thread to finish
        self.thread.join()

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle so we can't handle anything
        pass

    # runs inside a thread
    def _run(self):
        try:
            self.events.put({
                "data": {
                    "component": {"name": "agent:{}:worker".format(self.name)},
                    "severity": "OK",
                    "message": "clear",
                }
            })

            # try to start the server. this will block but we're in a thread.
            server_address = self.server.server_address
            self.logger.info("{} handler starting server on {}:{}".format(self.name, server_address[0], server_address[1]))
            self.server.serve_forever()
        except Exception as e:
            subject = "could not create coordination listener on {}: {}".format(self.fqdn, e)
            message = traceback.format_exc()
            self.logger.error("{} handler {}".format(self.name, subject))
            self.logger.error(message)

            self.events.put({
                "data": {
                    "component": {"name": "agent:{}:worker".format(self.name)},
                    "severity": 2,  # high severity
                    "title": subject,
                    "message": message,
                }
            })
