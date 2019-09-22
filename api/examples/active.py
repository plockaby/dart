#!/usr/bin/env python3

import requests
import json

data = [
    {
        'now': 1556774041,
        'name': 'cassandra-node-repair',
        'group': 'cassandra-node-repair',
        'description': 'May 01 10:10 PM',
        'pid': 0,
        'start': 1556773824,
        'stop': 1556773825,
        'exitstatus': 0,
        'spawnerr': '',
        'statename': 'EXITED',
        'state': 100,
        'logfile': '/data/logs/supervisor/cassandra-node-repair.log',
        'stdout_logfile': '/data/logs/supervisor/cassandra-node-repair.log',
        'stderr_logfile': '/data/logs/supervisor/cassandra-node-repair.err',
    }
]

endpoint = "https://localhost:274/dart/agent/v1/active/dev.lockaby.org"
cert = "/usr/local/ssl/certs/local/dart.local.lockaby.org.pem"
ca = "/usr/local/ssl/certs/local-ca.cert"
response = requests.post(endpoint, cert=cert, verify=ca, data=json.dumps(data))
response.raise_for_status()
