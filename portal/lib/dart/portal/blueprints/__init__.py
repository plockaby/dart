from flask import Blueprint
main = Blueprint("main", "dart.portal.blueprints.main", static_folder="static", template_folder="templates")
api = Blueprint("api", "dart.portal.blueprints.api", static_folder=None, template_folder=None)
