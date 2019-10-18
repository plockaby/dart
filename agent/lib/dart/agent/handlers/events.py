"""
This handler listens for TCP/Unix connections from the localhost and from this
agent sending us events. We will forward those events to the CorkAPI.
"""

from . import BaseHandler
from ..settings import SettingsManager
from dart.common.exceptions import EventValidationException
from threading import Thread
import socketserver
import requests
import traceback
import json
import os


class EventHandler(BaseHandler):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # configure settings
        self.settings = SettingsManager().get("events", {})
        self.settings["port"] = int(self.settings.get("port", 1337))
        self.settings["path"] = self.settings.get("path", "/run/events.sock")

        # where we are listening
        self.logger.info("{} handler listening for events on port {}".format(self.name, self.settings["port"]))
        self.logger.info("{} handler listening for events at path {}".format(self.name, self.settings["path"]))

        class TCPRequestServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            # faster re-binding
            allow_reuse_address = True

            # make this bigger than five
            request_queue_size = 10

            # kick connections when we exit
            daemon_threads = True

        class UnixStreamRequestServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            # faster re-binding
            allow_reuse_address = True

            # make this bigger than five
            request_queue_size = 10

            # kick connections when we exit
            daemon_threads = True

        class TCPRequestHandler(socketserver.StreamRequestHandler):
            def handle(subself):
                try:
                    data = subself.rfile.readline().strip()
                    self.logger.debug("{} handler received TCP event from {}:{}".format(self.name, subself.client_address[0], subself.client_address[1]))
                    try:
                        data = self._validate(data)
                        self.events.put(data)
                    except EventValidationException as e:
                        # if the event didn't validate then tell the caller why
                        result = json.dumps({
                            "accepted": False,
                            "error": str(e),
                        })
                        subself.wfile.write((result + "\n").encode())
                    else:
                        # tell our caller that we accepted the event
                        subself.wfile.write(('{"accepted": true}' + "\n").encode())
                except BrokenPipeError:
                    self.logger.debug("{} handler broken TCP pipe from {}:{}".format(self.name, subself.client_address[0], subself.client_address[1]))

        class UnixStreamRequestHandler(socketserver.StreamRequestHandler):
            def handle(subself):
                try:
                    data = subself.rfile.readline().strip()
                    self.logger.debug("{} handler received Unix event".format(self.name))
                    try:
                        data = self._validate(data)
                        self.events.put(data)
                    except EventValidationException as e:
                        # if the event didn't validate then tell the caller why
                        result = json.dumps({
                            "accepted": False,
                            "error": str(e),
                        })
                        subself.wfile.write((result + "\n").encode())
                    else:
                        # tell our caller that we accepted the event
                        subself.wfile.write(('{"accepted": true}' + "\n").encode())
                except BrokenPipeError:
                    self.logger.debug("{} handler broken pipe over Unix socket".format(self.name))

        # this is the server. it handles the sockets. it passes requests to the
        # listener (the second argument). the server will run in its own thread
        # so that we can kill it when we need to
        self.tcp_server = TCPRequestServer(("127.0.0.1", self.settings["port"]), TCPRequestHandler)

        # note that we're just removing whatever socket is already there. this
        # can be dangerous if something is still using the old socket. but it
        # is worse if our new process doesn't start.
        try:
            os.unlink(self.settings["path"])
        except FileNotFoundError as e:
            self.logger.debug("{} handler could not remove {}: {}".format(self.name, self.settings["path"], e))

        # then create the unix socket server and fix the permissions
        self.unix_server = UnixStreamRequestServer(self.settings["path"], UnixStreamRequestHandler)
        os.chmod(self.settings["path"], 0o777)

    @property
    def name(self):
        return "events"

    def start(self):
        self.tcp_thread = Thread(target=self._run_tcp)
        self.tcp_thread.start()

        self.unix_thread = Thread(target=self._run_unix)
        self.unix_thread.start()

        # then stop the queue so that we process all of the events
        self.events_thread = Thread(target=self._run_queue)
        self.events_thread.start()

    def stop(self):
        self.logger.info("{} handler received signal to stop".format(self.name))

        # tell the servers to stop
        self.tcp_server.shutdown()
        self.unix_server.shutdown()

        # then wait for the threads to finish
        self.tcp_thread.join()
        self.unix_thread.join()

        # then kill the queue and the thread in which it is running
        self.events.put(None)
        self.events.join()
        self.events_thread.join()

        # try to clean up our unix socket
        try:
            os.remove(self.settings["path"])
        except FileNotFoundError as e:
            self.logger.warning("{} handler could not remove {}: {}".format(self.name, self.settings["path"], e))
        except Exception as e:
            self.logger.error("{} handler could not remove {}: {}".format(self.name, self.settings["path"], e))

    def can_handle(self, event_type):
        # this handler wants nothing from supervisor
        return False

    def handle(self, event_type, event, data):
        # we never get passed anything to handle so we can't handle anything
        pass

    # this runs inside a thread
    def _run_tcp(self):
        try:
            # clear first. any error will be reraised
            self.events.put({
                "data": {
                    "component": {"name": "agent:{}:tcp-listener".format(self.name)},
                    "severity": "OK",
                    "message": "clear",
                }
            })

            # try to start the server. this will block but we're in a thread.
            server_address = self.tcp_server.server_address
            self.logger.info("{} handler starting TCP server on {}:{}".format(self.name, server_address[0], server_address[1]))
            self.tcp_server.serve_forever()
        except Exception as e:
            subject = "could not create TCP event listener on {}: {}".format(self.fqdn, e)
            message = traceback.format_exc()
            self.logger.error("{} handler {}".format(self.name, subject))
            self.logger.error(message)

            self.events.put({
                "data": {
                    "component": {"name": "agent:{}:tcp-listener".format(self.name)},
                    "severity": 2,  # high severity
                    "title": subject,
                    "message": message,
                }
            })

    # this runs inside of a thread
    def _run_unix(self):
        try:
            # clear first. any error will be reraised
            self.events.put({
                "data": {
                    "component": {"name": "agent:{}:unix-listener".format(self.name)},
                    "severity": "OK",
                    "message": "clear",
                }
            })

            # try to start the server. this will block but we're in a thread.
            server_address = self.unix_server.server_address
            self.logger.info("{} handler starting Unix server at {}".format(self.name, server_address))
            self.unix_server.serve_forever()
        except Exception as e:
            subject = "could not create Unix event listener on {}: {}".format(self.fqdn, e)
            message = traceback.format_exc()
            self.logger.error("{} handler {}".format(self.name, subject))
            self.logger.error(message)

            self.events.put({
                "environment": self.environment,
                "data": {
                    "component": {"name": "agent:{}:unix-listener".format(self.name)},
                    "severity": 2,  # high severity
                    "title": subject,
                    "message": message,
                }
            })

    def _run_queue(self):
        # loop forever -- after getting a message off of the queue on which we
        # are listening we send it to the CorkAPI and then wait for more.
        while (True):
            item = None
            try:
                # this will block while waiting for messages to appear on the
                # local thread queue. we immediately acknowledge it off of the
                # local thread queue so that if there is an exception then we
                # can put it back on the queue.
                item = self.events.get()
                self.events.task_done()

                # if "None" is put on the queue then we are to stop listening
                # to the queue. this happens when someone calls the ".stop"
                # method to this class.
                if (item is None):
                    self.logger.info("{} handler cleaning up before exit".format(self.name))
                    break

                # get some pieces out of the event that was enqueued
                event_data = item["data"]
                event_type = item.get("type", "event")  # determines API endpoint

                # if no hostname is provided then fill ours in
                if ("host" not in event_data or event_data["host"] is None):
                    event_data["host"] = {}
                if (not isinstance(event_data["host"], dict)):
                    event_data["host"] = {}
                if ("name" not in event_data["host"] or event_data["host"]["name"] is None):
                    event_data["host"]["name"] = self.fqdn

                # send the event to the API
                self.logger.debug("{} handler sending {} to CorkAPI".format(self.name, event_type))
                # TODO
            except requests.RequestException as e:
                self.logger.warning("{} handler could not talk to CorkAPI -- skipping: {}".format(self.name, e))

                # if we have an exception we're going to try to put it on the
                # queue later because maybe the CorkAPI will be working again.
                self.events.put(item)

    def _validate(self, packet):
        try:
            packet = json.loads(packet.decode("utf8", "backslashreplace"))

            # if the event is not a dict then throw it out
            if (not isinstance(packet, dict)):
                raise EventValidationException("You must send a JSON object to the CorkAPI agent.")

            # pull out the pieces we want
            event_type = packet.get("type", "event")
            event_data = packet.get("data", {})

            # validate the event type
            if (event_type.lower() not in ["event", "keepalive"]):
                self.logger.warning("{}: invalid value {} for type".format(self.name, event_type))
                raise EventValidationException("You may only use the types 'event' and 'keepalive'.")

            # if the event is not a dict then throw it out
            if (not isinstance(event_data, dict)):
                raise EventValidationException("You must send a JSON object to the CorkAPI agent.")

            return packet
        except UnicodeDecodeError as e:
            self.logger.warning("{}: event contained undecodable unicode data -- skipping: {}".format(self.name, e))
            raise EventValidationException("The CorkAPI agent received non-UTF-8 data that could not be decoded.  You must send data only in UTF-8.")
        except json.decoder.JSONDecodeError as e:
            self.logger.warning("{}: event contained undecodable json data -- skipping: {}".format(self.name, e))
            raise EventValidationException("The CorkAPI agent received non-JSON data that could not be parsed.  You must send only valid JSON data.")
        except Exception as e:
            self.logger.error("{}: error processing event -- skipping: {}".format(self.name, e))
            raise EventValidationException("The CorkAPI agent could not process your event.")