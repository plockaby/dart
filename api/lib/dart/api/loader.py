# need to monkey patch most libraries to work correctly with gevent/eventlet.
# this needs to happen as soon as possible, before any other code has loaded.
import dart.common.monkey
dart.common.monkey.patch()

# then load the program normally
from .app import load  # noqa: F402
app = load()
