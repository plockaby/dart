from ...app import logger
from ...app import cache
from ...app import api_manager
from . import autocomplete
from flask import make_response, jsonify, request
from werkzeug.exceptions import HTTPException
import traceback


@autocomplete.route("/host")
@cache.cached(timeout=30)
def host():
    try:
        url = "{}/tool/v1/hosts".format(api_manager.dart_api_url)
        response = api_manager.dart_api.get(url, timeout=10)
        response.raise_for_status()
        return make_response(jsonify(response.json()), 200)
    except Exception:
        logger.debug(traceback.format_exc())
        return make_response(jsonify([]), 200)


@autocomplete.route("/process")
@cache.cached(timeout=30)
def process_name():
    try:
        url = "{}/tool/v1/processes".format(api_manager.dart_api_url)
        response = api_manager.dart_api.get(url, timeout=10)
        response.raise_for_status()
        return make_response(jsonify(response.json()), 200)
    except Exception:
        logger.debug(traceback.format_exc())
        return make_response(jsonify([]), 200)
