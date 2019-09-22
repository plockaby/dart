#!/usr/bin/env python3

import requests
import pprint


endpoint = "https://localhost:274/dart/agent/v1/assigned/dev.lockaby.org"
cert = "/usr/local/ssl/certs/local/dart.local.lockaby.org.pem"
ca = "/usr/local/ssl/certs/local-ca.cert"
response = requests.get(endpoint, cert=cert, verify=ca)

pp = pprint.PrettyPrinter()
pp.pprint(response.json())
