from django.core.exceptions import ValidationError

class ConcurrencyError(ValidationError):
    """Raised when an optimistic lock fails due to concurrent modification."""
    pass
