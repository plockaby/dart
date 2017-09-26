from flask import Blueprint
main = Blueprint("main", "dart.web.main", static_folder="static", template_folder="templates")
api_commands = Blueprint("api.commands", "dart.web.api.commands", static_folder=None, template_folder=None)
api_actions = Blueprint("api.actions", "dart.web.api.actions", static_folder=None, template_folder=None)
api_hosts = Blueprint("api.hosts", "dart.web.api.hosts", static_folder=None, template_folder=None)
api_processes = Blueprint("api.processes", "dart.web.api.processes", static_folder=None, template_folder=None)
