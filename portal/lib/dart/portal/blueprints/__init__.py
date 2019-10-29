from flask import Blueprint
main = Blueprint("main", "dart.portal.blueprints.main", static_folder="static", template_folder="templates")
autocomplete = Blueprint("autocomplete", "dart.portal.blueprints.autocomplete", static_folder=None, template_folder=None)
api = Blueprint("api", "dart.portal.blueprints.api", static_folder=None, template_folder=None)
