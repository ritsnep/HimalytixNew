from django.core.management.base import BaseCommand
from django.db import transaction

from usermanagement.models import (
    Entity,
    Module,
    Organization,
    Permission,
    Role,
)


SPECIAL_PERMISSION_DEFINITIONS = [
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'submit_journal',
        'name': 'Can submit journal entries',
        'description': 'Allows submitting journals for approval.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'approve_journal',
        'name': 'Can approve journal entries',
        'description': 'Allows approving journals awaiting approval.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'reject_journal',
        'name': 'Can reject journal entries',
        'description': 'Allows rejecting journals awaiting approval.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'post_journal',
        'name': 'Can post journal entries',
        'description': 'Allows posting approved journals to the general ledger.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'reverse_journal',
        'name': 'Can reverse journal entries',
        'description': 'Allows reversing previously posted journals.',
    },
    {
        'module': 'accounting',
        'entity': 'accountingperiod',
        'action': 'close_period',
        'name': 'Can close accounting periods',
        'description': 'Allows closing open accounting periods.',
    },
    {
        'module': 'accounting',
        'entity': 'accountingperiod',
        'action': 'reopen_period',
        'name': 'Can reopen accounting periods',
        'description': 'Allows reopening previously closed periods.',
    },
    {
        'module': 'accounting',
        'entity': 'fiscalyear',
        'action': 'close_fiscalyear',
        'name': 'Can close fiscal years',
        'description': 'Allows closing a fiscal year.',
    },
    {
        'module': 'accounting',
        'entity': 'fiscalyear',
        'action': 'reopen_fiscalyear',
        'name': 'Can reopen fiscal years',
        'description': 'Allows reopening a closed fiscal year.',
    },
]


ROLE_DEFINITIONS = {
    'ADMIN': {
        'name': 'Admin',
        'description': 'Full access to all features.',
    },
    'CLERK': {
        'name': 'Clerk',
        'description': 'Clerk with create/edit access to transactions.',
    },
    'MANAGER': {
        'name': 'Manager',
        'description': 'Manager with approval and period closing rights.',
    },
    'AUDITOR': {
        'name': 'Auditor',
        'description': 'Auditor with read-only access.',
    },
}


class Command(BaseCommand):
    help = 'Sets up system roles (Admin, Clerk, Manager, Auditor) and assigns permissions for each organization.'

    def handle(self, *args, **kwargs):
        accounting_module, _ = Module.objects.get_or_create(
            code='accounting',
            defaults={
                'name': 'Accounting',
                'description': 'Accounting module',
            },
        )

        # Ensure required entities exist
        required_entities = {
            'journal': 'Journal Entry management',
            'accountingperiod': 'Accounting Period management',
            'fiscalyear': 'Fiscal Year management',
        }
        entities = {}
        for code, description in required_entities.items():
            entity, _ = Entity.objects.get_or_create(
                module=accounting_module,
                code=code,
                defaults={
                    'name': code.replace('_', ' ').title(),
                    'description': description,
                    'is_active': True,
                },
            )
            entities[code] = entity

        # Ensure custom permissions exist
        for definition in SPECIAL_PERMISSION_DEFINITIONS:
            module = Module.objects.get(code=definition['module'])
            entity = Entity.objects.get(module=module, code=definition['entity'])
            Permission.objects.get_or_create(
                module=module,
                entity=entity,
                action=definition['action'],
                defaults={
                    'name': definition['name'],
                    'description': definition['description'],
                    'is_active': True,
                },
            )

        organizations = Organization.objects.all()
        all_permissions = Permission.objects.filter(is_active=True)
        accounting_view_permissions = set(
            Permission.objects.filter(
            module=accounting_module,
            action='view',
            is_active=True,
        ))
        journal_crud_permissions = set(
            Permission.objects.filter(
            module=accounting_module,
            entity=entities['journal'],
            action__in=['view', 'add', 'change', 'delete'],
            is_active=True,
        ))

        clerk_extra_permissions = set(
            Permission.objects.filter(
            module=accounting_module,
            entity=entities['journal'],
            action='submit_journal',
        ))

        manager_special_permissions = set(
            Permission.objects.filter(
            codename__in=[
                'accounting_journal_approve_journal',
                'accounting_journal_reject_journal',
                'accounting_journal_post_journal',
                'accounting_journal_reverse_journal',
                'accounting_accountingperiod_close_period',
                'accounting_accountingperiod_reopen_period',
                'accounting_fiscalyear_close_fiscalyear',
                'accounting_fiscalyear_reopen_fiscalyear',
            ]
        ))

        auditor_permissions = set(accounting_view_permissions)

        for org in organizations:
            with transaction.atomic():
                admin_role, _ = Role.objects.update_or_create(
                    code='ADMIN',
                    organization=org,
                    defaults={
                        'name': ROLE_DEFINITIONS['ADMIN']['name'],
                        'description': ROLE_DEFINITIONS['ADMIN']['description'],
                        'is_system': True,
                        'is_active': True,
                    },
                )
                admin_role.permissions.set(all_permissions)

                clerk_role, _ = Role.objects.update_or_create(
                    code='CLERK',
                    organization=org,
                    defaults={
                        'name': ROLE_DEFINITIONS['CLERK']['name'],
                        'description': ROLE_DEFINITIONS['CLERK']['description'],
                        'is_system': True,
                        'is_active': True,
                    },
                )
                clerk_permissions = accounting_view_permissions | journal_crud_permissions | clerk_extra_permissions
                clerk_role.permissions.set(clerk_permissions)

                manager_role, _ = Role.objects.update_or_create(
                    code='MANAGER',
                    organization=org,
                    defaults={
                        'name': ROLE_DEFINITIONS['MANAGER']['name'],
                        'description': ROLE_DEFINITIONS['MANAGER']['description'],
                        'is_system': True,
                        'is_active': True,
                    },
                )
                manager_permissions = accounting_view_permissions | journal_crud_permissions | manager_special_permissions
                manager_role.permissions.set(manager_permissions)

                auditor_role, _ = Role.objects.update_or_create(
                    code='AUDITOR',
                    organization=org,
                    defaults={
                        'name': ROLE_DEFINITIONS['AUDITOR']['name'],
                        'description': ROLE_DEFINITIONS['AUDITOR']['description'],
                        'is_system': True,
                        'is_active': True,
                    },
                )
                auditor_role.permissions.set(auditor_permissions)

            self.stdout.write(
                self.style.SUCCESS(
                    f"System roles configured for organization: {org.name}"
                )
            )
