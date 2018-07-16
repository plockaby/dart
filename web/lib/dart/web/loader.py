# need to monkey patch to make cassandra work and monkey patching needs
# to happen super early in the loading of the system. by doing it here it
# happens before any code is really run.
import dart.common.monkey
dart.common.monkey.patch()

# then load the program normally
from . import load  # noqa: F402
app = load()
