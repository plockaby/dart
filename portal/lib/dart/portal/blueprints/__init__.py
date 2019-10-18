from flask import Blueprint
api = Blueprint("api", "dart.portal.blueprints.api", static_folder=None, template_folder=None)
main = Blueprint("main", "dart.portal.blueprints.main", static_folder="static", template_folder="templates")
