# the order of imports is important here. "views" uses "api"
# so "api" must be imported before "views".
from .. import api  # noqa: F401
from . import views  # noqa: F401
