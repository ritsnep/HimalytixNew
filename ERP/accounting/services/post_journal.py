import logging
from typing import Optional

from django.core.exceptions import PermissionDenied, ValidationError

from accounting.models import Journal
from accounting.services.posting_service import PostingService

logger = logging.getLogger(__name__)


class JournalError(Exception):
    """Base exception for journal-related errors."""


class JournalValidationError(JournalError, ValidationError):
    """Specific validation error for journal entries."""


class JournalPostingError(JournalError):
    """Error during journal posting process."""


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
