from rest_framework import permissions


class CanCreateInvoice(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("billing.add_invoiceheader")


class CanCancelInvoice(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("billing.change_invoiceheader")


class CanViewAuditLog(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("billing.view_invoiceauditlog")
