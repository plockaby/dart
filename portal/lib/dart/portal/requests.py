from .app import logger
from .app import api_manager
from datetime import datetime
import urllib.parse
import json


def select_hosts():
    url = "{}/tool/v1/hosts".format(api_manager.dart_api_url)
    response = api_manager.dart_api.get(url, timeout=10)
    response.raise_for_status()

    # convert string timestamp to a datetime object
    results = []
    for result in response.json():
        try:
            result["polled"] = datetime.strptime(result.get("polled"), "%Y-%m-%d %H:%M:%S")
        except Exception:
            result["polled"] = None
        results.append(result)

    return results


def select_host(fqdn):
    url = "{}/tool/v1/hosts/{}".format(api_manager.dart_api_url, urllib.parse.quote(fqdn))
    response = api_manager.dart_api.get(url, timeout=10)

    # if host doesn't exist we get a 404, don't raise exception
    if (response.status_code == 404):
        return

    response.raise_for_status()
    result = response.json()

    # convert some timestamps
    try:
        result["polled"] = datetime.strptime(result.get("polled"), "%Y-%m-%d %H:%M:%S")
    except Exception:
        result["polled"] = None
    try:
        result["booted"] = datetime.strptime(result.get("booted"), "%Y-%m-%d %H:%M:%S")
    except Exception:
        result["booted"] = None

    return result


def delete_host(fqdn):
    url = "{}/tool/v1/hosts/{}".format(api_manager.dart_api_url, urllib.parse.quote(fqdn))
    response = api_manager.dart_api.delete(url, timeout=10)
    response.raise_for_status()
    return response.json()


def select_processes():
    url = "{}/tool/v1/processes".format(api_manager.dart_api_url)
    response = api_manager.dart_api.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def select_process(process_name):
    url = "{}/tool/v1/processes/{}".format(api_manager.dart_api_url, urllib.parse.quote(process_name))
    response = api_manager.dart_api.get(url, timeout=10)

    # if process doesn't exist we get a 404, don't raise exception
    if (response.status_code == 404):
        return

    response.raise_for_status()
    return response.json()


def delete_process(process_name):
    url = "{}/tool/v1/processes/{}".format(api_manager.dart_api_url, urllib.parse.quote(process_name))
    response = api_manager.dart_api.delete(url, timeout=10)
    response.raise_for_status()
    return response.json()


def send_host_command(fqdn, command):
    url = "{}/coordination/v1/{}/{}".format(api_manager.dart_api_url, urllib.parse.quote(command), urllib.parse.quote(fqdn))
    response = api_manager.dart_api.post(url, timeout=10)
    response.raise_for_status()


def send_process_command(fqdn, process_name, command):
    url = "{}/coordination/v1/{}/{}/{}".format(api_manager.dart_api_url, urllib.parse.quote(command), urllib.parse.quote(fqdn), urllib.parse.quote(process_name))
    response = api_manager.dart_api.post(url, timeout=10)
    response.raise_for_status()


def enable_process(fqdn, process_name):
    logger.info("enabling {} on {}".format(process_name, fqdn))
    data = {
        "op": "replace",
        "path": "/assignments",
        "value": {
            "fqdn": fqdn,
            "disabled": False,
        }
    }

    # patch the configuration
    url = "{}/tool/v1/processes/{}".format(api_manager.dart_api_url, urllib.parse.quote(process_name))
    response = api_manager.dart_api.patch(url, data=json.dumps(data), timeout=10)
    response.raise_for_status()

    try:
        # tell the remote system to rewrite its configuration
        send_host_command(fqdn, "rewrite")
    except Exception:
        pass


def disable_process(fqdn, process_name):
    logger.info("disabling {} on {}".format(process_name, fqdn))
    data = {
        "op": "replace",
        "path": "/assignments",
        "value": {
            "fqdn": fqdn,
            "disabled": True,
        }
    }

    # patch the configuration
    url = "{}/tool/v1/processes/{}".format(api_manager.dart_api_url, urllib.parse.quote(process_name))
    response = api_manager.dart_api.patch(url, data=json.dumps(data), timeout=10)
    response.raise_for_status()

    try:
        # tell the remote system to rewrite its configuration
        send_host_command(fqdn, "rewrite")
    except Exception:
        pass


def assign_process(fqdn, process_name, process_environment):
    logger.info("assigning {} {} to {}".format(process_name, process_environment, fqdn))
    data = {
        "op": "add",
        "path": "/assignments",
        "value": {
            "name": process_name,
            "environment": process_environment,
        }
    }

    # patch the configuration
    url = "{}/tool/v1/hosts/{}".format(api_manager.dart_api_url, urllib.parse.quote(fqdn))
    response = api_manager.dart_api.patch(url, data=json.dumps(data), timeout=10)
    response.raise_for_status()

    try:
        # tell the remote system to rewrite its configuration
        send_host_command(fqdn, "rewrite")
    except Exception:
        pass


def unassign_process(fqdn, process_name):
    logger.info("unassigning {} from {}".format(process_name, fqdn))
    data = {
        "op": "remove",
        "path": "/assignments",
        "value": {
            "name": process_name,
        }
    }

    # patch the configuration
    url = "{}/tool/v1/hosts/{}".format(api_manager.dart_api_url, urllib.parse.quote(fqdn))
    response = api_manager.dart_api.patch(url, data=json.dumps(data), timeout=10)
    response.raise_for_status()

    try:
        # tell the remote system to rewrite its configuration
        send_host_command(fqdn, "rewrite")
    except Exception:
        pass


def register(data):
    url = "{}/tool/v1/register".format(api_manager.dart_api_url)
    response = api_manager.dart_api.post(url, data=json.dumps(data), timeout=60)
    response.raise_for_status()
    return response.json()
