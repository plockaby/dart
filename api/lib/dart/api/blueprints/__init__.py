from flask import Blueprint
tool_v1 = Blueprint("tool_v1", "dart.api.blueprints.tool.v1", static_folder=None, template_folder=None)
agent_v1 = Blueprint("agent_v1", "dart.api.blueprints.agent.v1", static_folder=None, template_folder=None)
coordination_v1 = Blueprint("coordination_v1", "dart.api.blueprints.coordination.v1", static_folder=None, template_folder=None)
