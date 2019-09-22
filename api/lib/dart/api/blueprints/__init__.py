from flask import Blueprint
agent_v1 = Blueprint("agent_v1", "dart.api.blueprints.agent.v1", static_folder=None, template_folder=None)
portal_v1 = Blueprint("portal_v1", "dart.api.blueprints.portal.v1", static_folder=None, template_folder=None)
