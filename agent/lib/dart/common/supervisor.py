import http.client
import xmlrpc.client
import socket


class SupervisorClient(object):
    def __init__(self, supervisor_server_url):
        # try to get a connection to supervisord
        if (supervisor_server_url.startswith("unix://")):
            # must remove the "unix://" prefix to just get the raw path
            self.client = xmlrpc.client.ServerProxy("http://localhost:9001", transport=UnixStreamTransport(supervisor_server_url[7:]))
        else:
            # just connect over a generic inet socket
            self.client = xmlrpc.client.ServerProxy(supervisor_server_url)

    @property
    def connection(self):
        return self.client


# used by the UnixStreamTransport
class UnixStreamHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


# used by anything that connects to supervisor over a unix socket
class UnixStreamTransport(xmlrpc.client.Transport):
    def __init__(self, socket_path):
        self.socket_path = socket_path
        super(UnixStreamTransport, self).__init__()

    def make_connection(self, host):
        return UnixStreamHTTPConnection(self.socket_path)
