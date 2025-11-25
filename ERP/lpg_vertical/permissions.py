from rest_framework import permissions

from lpg_vertical.services import get_company_config


class FeaturePermission(permissions.BasePermission):
    required_feature = None
    allowed_roles = {"admin", "manager", "accountant", "superadmin", "data_entry"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        org = getattr(request, "organization", None) or getattr(user, "organization", None)
        if org is None:
            return False

        config = get_company_config(org)
        if self.required_feature and not getattr(config, self.required_feature, False):
            return False

        if self.allowed_roles and getattr(user, "role", None) not in self.allowed_roles:
            return False

        return True


class NocPermission(FeaturePermission):
    required_feature = "enable_noc_purchases"
    allowed_roles = {"admin", "manager", "accountant", "superadmin"}


class SalesPermission(FeaturePermission):
    required_feature = "enable_dealer_management"
    allowed_roles = {"admin", "manager", "accountant", "data_entry", "superadmin"}


class LogisticsPermission(FeaturePermission):
    required_feature = "enable_logistics"
    allowed_roles = {"admin", "manager", "accountant", "superadmin"}
