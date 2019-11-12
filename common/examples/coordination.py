#!/usr/bin/env python3

import socket
import json
import ssl


ctx = ssl.SSLContext()
ctx.verify_mode = ssl.CERT_REQUIRED
ctx.check_hostname = True
ctx.load_verify_locations("/usr/local/ssl/certs/local-ca.cert")
ctx.load_cert_chain("/usr/local/ssl/certs/local/dart.local.lockaby.org.pem")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    with ctx.wrap_socket(sock, server_hostname="dart.local.lockaby.org") as ssock:
        ssock.connect(("127.0.0.1", 3278))
        ssock.sendall((json.dumps({"action": "reread"}) + "\n").encode())
