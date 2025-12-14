import logging
from typing import Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, DatabaseError

from accounting.models import Journal
from accounting.services.posting_service import PostingService

logger = logging.getLogger(__name__)


class JournalError(Exception):
    """Base exception for journal-related errors."""


class JournalValidationError(JournalError, ValidationError):
    """Specific validation error for journal entries."""


class JournalPostingError(JournalError):
    """Error during journal posting process."""


def format_journal_exception(exc: Exception) -> str:
    """Return a user-friendly message for journal-related exceptions.

    This centralizes mapping of internal exception details to messages shown
    to end users or returned by APIs. Keep messages concise and safe to
    display (avoid leaking internal tracebacks).
    """
    # Validation errors typically have .messages or are safe to present
    try:
        from django.core.exceptions import ValidationError as DjangoValidationError
    except Exception:
        DjangoValidationError = None

    # If it's our wrapped JournalValidationError, prefer its messages
    if DjangoValidationError is not None and isinstance(exc, DjangoValidationError):
        # ValidationError.messages may be a list
        msgs = getattr(exc, 'messages', None)
        if msgs:
            if isinstance(msgs, (list, tuple)):
                return '; '.join(str(m) for m in msgs)
            return str(msgs)
        # Fallback to string representation
        return str(exc)

    # JournalPostingError: provide the message if set, otherwise generic
    if isinstance(exc, JournalPostingError):
        text = str(exc) if str(exc) else 'An error occurred while posting the journal.'
        return text

    # Generic fallback
    return str(exc) or 'An error occurred while processing the request.'


def _resolve_user(journal: Journal, user: Optional[object]):
    if user is not None:
        return user
    if getattr(journal, "updated_by", None):
        return journal.updated_by
    if getattr(journal, "created_by", None):
        return journal.created_by
    return None


def post_journal(journal: Journal, user=None) -> Journal:
    """
    Legacy helper that delegates to the PostingService while preserving
    historical exception types for callers that still depend on them.
    """
    logger.info("Delegating journal %s posting to PostingService", journal.pk)
    service = PostingService(_resolve_user(journal, user))
    try:
        posted = service.post(journal)
        return posted
    except ValidationError as exc:
        logger.error("Validation error while posting journal %s: %s", journal.pk, exc)
        raise JournalValidationError(exc.messages) from exc
    except PermissionDenied as exc:
        logger.error("Permission denied while posting journal %s: %s", journal.pk, exc)
        raise JournalPostingError(str(exc)) from exc
    except IntegrityError as exc:
        # Database integrity errors can be caused by concurrent posting attempts
        # or by other DB-level conflicts. Attempt to detect a concurrent
        # successful post: if the journal is now posted, return it idempotently.
        logger.exception("Integrity error while posting journal %s: %s", journal.pk, exc)
        try:
            current = Journal.objects.filter(pk=journal.pk).first()
            if current and getattr(current, "status", None) == "posted":
                logger.info("Detected concurrent post for journal %s; returning posted journal", journal.pk)
                return current
        except Exception:
            logger.exception("Failed to reload journal %s after IntegrityError", journal.pk)
        raise JournalPostingError("A database integrity error occurred while posting the journal.") from exc
    except DatabaseError as exc:
        logger.exception("Database error while posting journal %s: %s", journal.pk, exc)
        raise JournalPostingError("A database error occurred while posting the journal.") from exc
    except Exception as exc:
        logger.exception("Unexpected error while posting journal %s: %s", journal.pk, exc)
        raise JournalPostingError("An unexpected error occurred while posting the journal.") from exc
