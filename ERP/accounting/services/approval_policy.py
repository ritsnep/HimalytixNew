from __future__ import annotations

from typing import Optional

from accounting.models import ApprovalWorkflow
from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService


class ApprovalPolicyService:
    """Resolves the default approval workflow per area from configuration."""

    CONFIG_KEY = "approval_workflows"

    def __init__(self, organization):
        self.organization = organization

    def _load_policy(self) -> dict:
        return (
            ConfigurationService.get_value(
                organization=self.organization,
                scope=ConfigurationEntry.SCOPE_FINANCE,
                key=self.CONFIG_KEY,
                default={},
            )
            or {}
        )

    def get_default_workflow(self, area: str) -> Optional[ApprovalWorkflow]:
        policy = self._load_policy()
        workflow_name = policy.get(area)
        queryset = ApprovalWorkflow.objects.filter(
            organization=self.organization,
            area=area,
            active=True,
        )
        if workflow_name:
            workflow = queryset.filter(name=workflow_name).first()
            if workflow:
                return workflow
        return queryset.order_by("name").first()
