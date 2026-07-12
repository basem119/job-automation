class ApplicationError(Exception):
    """Base exception for application-level failures."""


class ConfigurationError(ApplicationError):
    """Raised when configuration cannot be safely loaded."""
