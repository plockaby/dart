# the order of imports is important here. "views" uses "autocomplete"
# so "autocomplete" must be imported before "views".
from .. import autocomplete  # noqa: F401
from . import views  # noqa: F401
