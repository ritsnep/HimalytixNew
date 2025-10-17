from django.urls import path
from components.core.views_htmx import HtmxTableView
from django.contrib.auth import get_user_model

User = get_user_model()

class UserTableView(HtmxTableView):
    model = User
    template_name = 'components/base/table_htmx.html'
    context_object_name = 'object_list'
    
    columns = [
        {
            'name': 'username',
            'label': 'Username',
            'sortable': True,
        },
        {
            'name': 'email',
            'label': 'Email',
            'sortable': True,
        },
        {
            'name': 'date_joined',
            'label': 'Date Joined',
            'sortable': True,
            'align': 'center',
        },
        {
            'name': 'is_active',
            'label': 'Active',
            'sortable': True,
            'align': 'center',
        }
    ]
    
    filter_config = {
        'filters': {
            'username': {
                'type': 'text',
                'label': 'Username',
                'placeholder': 'Search username...'
            },
            'is_active': {
                'type': 'select',
                'label': 'Status',
                'choices': [
                    {'value': '1', 'label': 'Active'},
                    {'value': '0', 'label': 'Inactive'}
                ]
            },
            'date_joined': {
                'type': 'daterange',
                'label': 'Date Joined'
            }
        }
    }
    
    bulk_actions = [
        {
            'name': 'activate',
            'label': 'Activate Users',
            'icon': 'fas fa-check',
            'confirm': 'Are you sure you want to activate selected users?'
        },
        {
            'name': 'deactivate',
            'label': 'Deactivate Users',
            'icon': 'fas fa-times',
            'confirm': 'Are you sure you want to deactivate selected users?'
        }
    ]
    
    row_actions = [
        {
            'label': 'Edit',
            'icon': 'fas fa-edit',
            'url': 'admin:auth_user_change',
            'style': 'primary',
            'icon_only': True
        },
        {
            'label': 'Delete',
            'icon': 'fas fa-trash',
            'url': 'admin:auth_user_delete',
            'style': 'danger',
            'icon_only': True,
            'confirm': 'Are you sure you want to delete this user?'
        }
    ]
    
    export_formats = [
        {
            'name': 'csv',
            'label': 'CSV',
            'icon': 'fas fa-file-csv'
        },
        {
            'name': 'excel',
            'label': 'Excel',
            'icon': 'fas fa-file-excel'
        }
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        filters = {}
        
        username = self.request.GET.get('username')
        if username:
            filters['username__icontains'] = username
            
        is_active = self.request.GET.get('is_active')
        if is_active:
            filters['is_active'] = is_active == '1'
            
        date_from = self.request.GET.get('date_joined_from')
        if date_from:
            filters['date_joined__gte'] = date_from
            
        date_to = self.request.GET.get('date_joined_to')
        if date_to:
            filters['date_joined__lte'] = date_to
            
        return queryset.filter(**filters)

    def bulk_activate(self, items):
        """Handle bulk activate action."""
        User.objects.filter(id__in=items).update(is_active=True)
        return {
            'message': f'Successfully activated {len(items)} users'
        }
        
    def bulk_deactivate(self, items):
        """Handle bulk deactivate action."""
        User.objects.filter(id__in=items).update(is_active=False)
        return {
            'message': f'Successfully deactivated {len(items)} users'
        }
