class DartInvalidTagException(ValueError):
    """This is raised when the given tag is not valid."""
    pass


class DartHostDoesNotExistException(ValueError):
    """This is raised when the given host does not exist."""
    pass


class DartProcessDoesNotExistException(ValueError):
    """This is raised when the given process does not exist."""
    pass


class DartProcessEnvironmentDoesNotExistException(ValueError):
    """This is raised when the given process does not exist with the given environment name."""
    pass


class DartProcessNotAssignedException(ValueError):
    """This is raised when a process is not assigned to the given host."""
    pass
