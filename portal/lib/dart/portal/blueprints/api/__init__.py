# the order of imports is important here. "views" uses "v1"
# so "v1" must be imported before "views".
from .. import api  # noqa: F401
from . import views  # noqa: F401
