from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from django.db import transaction
from django.utils import timezone

from ..models import TransactionTypeConfig

CollisionChecker = Callable[[str], bool]


class DocumentNumberService:
    """Generates robust document numbers using prefix/suffix/restart rules."""

    MAX_ATTEMPTS = 1000

    @staticmethod
    def generate_next_number(
        config: TransactionTypeConfig,
        effective_date: Optional[date] = None,
        collision_check: Optional[CollisionChecker] = None,
    ) -> str:
        """Return the next available document number for the given configuration."""
        effective_date = effective_date or timezone.localdate()

        with transaction.atomic():
            config = TransactionTypeConfig.objects.select_for_update().get(pk=config.pk)
            current_seq = max(config.sequence_next, config.start_number)

            restart_rule = DocumentNumberService._resolve_rule(
                config.restart_rules, effective_date
            )
            if restart_rule and config.last_restart_trigger != restart_rule.applicable_from:
                current_seq = restart_rule.restart_from
                config.last_restart_trigger = restart_rule.applicable_from

            if current_seq < config.start_number:
                current_seq = config.start_number

            attempts = 0
            candidate_number = None
            prefix = DocumentNumberService._resolve_prefix(config, effective_date)
            suffix = DocumentNumberService._resolve_suffix(config, effective_date)

            while attempts < DocumentNumberService.MAX_ATTEMPTS:
                padded_sequence = str(current_seq).zfill(config.zero_padding)
                candidate_number = f"{prefix}{padded_sequence}{suffix}"

                if not collision_check or not collision_check(candidate_number):
                    config.sequence_next = current_seq + 1
                    config.last_sequence_date = effective_date
                    config.save(update_fields=['sequence_next', 'last_sequence_date', 'last_restart_trigger'])
                    return candidate_number

                current_seq += 1
                attempts += 1

            raise RuntimeError("Unable to generate unique document number after max retries")

    @staticmethod
    def _resolve_prefix(config: TransactionTypeConfig, effective_date: date) -> str:
        rule_value = DocumentNumberService._resolve_rule(
            config.prefix_rules, effective_date, attr_name='prefix'
        )
        if rule_value:
            return rule_value
        return config.prefix_template or ''

    @staticmethod
    def _resolve_suffix(config: TransactionTypeConfig, effective_date: date) -> str:
        rule_value = DocumentNumberService._resolve_rule(
            config.suffix_rules, effective_date, attr_name='suffix'
        )
        if rule_value:
            return rule_value
        return config.suffix_template or ''

    @staticmethod
    def _resolve_rule(
        rules_query, effective_date: date, attr_name: str = ''
    ) -> Optional[str]:
        rule = rules_query.filter(applicable_from__lte=effective_date).order_by('-applicable_from').first()
        if not rule:
            return None
        if attr_name:
            return getattr(rule, attr_name)
        return rule
*** End Payload