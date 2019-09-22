class EventValidationException(Exception):
    """This is raised when an event didn't validate."""
    pass


class CommandValidationException(Exception):
    """This is raised when we've received an invalid command."""
    pass
