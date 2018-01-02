from . import loader
from .loader import logger, moment, db_client  # noqa: F401


# this makes the application available to things like gunicorn to run
app = loader.load()
