from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Sequence

from django.core.exceptions import ValidationError

from accounting.models import Journal
from accounting.services.posting_service import PostingService

logger = logging.getLogger(__name__)


class BatchPostingService:
    """
    Coordinates high-volume journal posting in controlled batches.

    The service enforces tenant scoping, feeds journals through the
    PostingService, and surfaces a deterministic summary so callers can
    reconcile successes vs. failures.
    """

    def __init__(self, user, organization=None):
        self.user = user
        self.organization = (
            organization
            or getattr(user, "get_active_organization", lambda: getattr(user, "organization", None))()
        )
        self.posting_service = PostingService(user)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def _base_queryset(self):
        qs = Journal.objects.all()
        if self.organization:
            qs = qs.filter(organization=self.organization)
        return qs

    def _ready_queryset(
        self,
        *,
        journal_ids: Optional[Sequence[int]] = None,
        limit: Optional[int] = 100,
    ):
        qs = self._base_queryset().select_related("journal_type", "period", "organization")
        if journal_ids:
            qs = qs.filter(pk__in=journal_ids)
        else:
            qs = qs.filter(status__in=["approved"], is_locked=False)
        qs = qs.order_by("journal_date", "journal_id")
        if limit:
            qs = qs[: limit]
        return qs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def post_journals(
        self,
        *,
        journal_ids: Optional[Sequence[int]] = None,
        limit: Optional[int] = 100,
        chunk_size: int = 50,
    ) -> dict:
        """
        Post journals in batches, returning a summary of successes/failures.
        """
        posted: List[int] = []
        failed: List[dict] = []
        queryset = self._ready_queryset(journal_ids=journal_ids, limit=limit)
        for journal in queryset.iterator(chunk_size=chunk_size):
            try:
                self.posting_service.post(journal)
            except ValidationError as exc:
                logger.warning(
                    "batch_posting.failed",
                    extra={"journal_id": journal.pk, "error": str(exc)},
                )
                failed.append({"journal_id": journal.pk, "error": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("batch_posting.unexpected", extra={"journal_id": journal.pk})
                failed.append({"journal_id": journal.pk, "error": str(exc)})
            else:
                posted.append(journal.pk)
        return {"posted": posted, "failed": failed}
