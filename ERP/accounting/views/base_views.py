from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from usermanagement.utils import PermissionUtils
from accounting.views.views_mixins import UserOrganizationMixin

class BaseListView(UserOrganizationMixin, ListView):
    paginate_by = 20
    permission_required = None

    def get_queryset(self):
        org = self.get_organization()
        if not org:
            return self.model.objects.none()
        return super().get_queryset().filter(organization=org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = self.get_organization()

        if self.permission_required:
            app_label, model_name, action = self.permission_required
            context['can_add'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'add')
            context['can_change'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'change')
            context['can_delete'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'delete')

        context['page_title'] = self.model._meta.verbose_name_plural.title()
        return context