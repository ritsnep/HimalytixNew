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

JOURNAL_META_PERMISSION_MAP = [
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'add',
        'name': 'Can add voucher entry',
        'description': 'Allows creating voucher entries.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'change',
        'name': 'Can change voucher entry',
        'description': 'Allows editing voucher entries.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'delete',
        'name': 'Can delete voucher entry',
        'description': 'Allows deleting voucher entries.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'view',
        'name': 'Can view voucher entry',
        'description': 'Allows viewing voucher entries.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'submit_journal',
        'name': 'Can submit journal for approval',
        'description': 'Allows submitting journals for approval.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'approve_journal',
        'name': 'Can approve journal',
        'description': 'Allows approving journals.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'post_journal',
        'name': 'Can post journal',
        'description': 'Allows posting journals.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'reverse_journal',
        'name': 'Can reverse journal',
        'description': 'Allows reversing journals.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'reject_journal',
        'name': 'Can reject journal',
        'description': 'Allows rejecting journals.',
    },
    {
        'module': 'accounting',
        'entity': 'journal',
        'action': 'change',
        'name': 'Can edit journal',
        'description': 'Allows editing journals.',
    },
    {
        'module': 'accounting',
        'entity': 'accountingperiod',
        'action': 'reopen_period',
        'name': 'Can reopen accounting period',
        'description': 'Allows reopening accounting periods.',
    },
]

PURCHASING_PERMISSION_DEFINITIONS = [
    {
        'module': 'purchasing',
        'entity': 'purchaseinvoice',
        'action': 'view',
        'name': 'Can view purchase invoices',
        'description': 'Allows viewing purchase invoices.',
    },
    {
        'module': 'purchasing',
        'entity': 'purchaseinvoice',
        'action': 'add',
        'name': 'Can add purchase invoices',
        'description': 'Allows creating purchase invoices.',
    },
    {
        'module': 'purchasing',
        'entity': 'purchaseinvoice',
        'action': 'change',
        'name': 'Can change purchase invoices',
        'description': 'Allows editing purchase invoices and landed cost documents.',
    },
    {
        'module': 'purchasing',
        'entity': 'purchaseinvoice',
        'action': 'delete',
        'name': 'Can delete purchase invoices',
        'description': 'Allows deleting purchase invoices.',
    },
    {
        'module': 'purchasing',
        'entity': 'purchaseinvoice',
        'action': 'post',
        'name': 'Can post purchase invoices',
        'description': 'Allows posting purchase invoices and applying landed costs.',
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
        purchasing_module, _ = Module.objects.get_or_create(
            code='purchasing',
            defaults={
                'name': 'Purchasing',
                'description': 'Purchasing and procurement',
            },
        )

        module_map = {
            'accounting': accounting_module,
            'purchasing': purchasing_module,
        }

        # Ensure required entities exist
        required_entities = {
            'journal': 'Journal Entry management',
            'accountingperiod': 'Accounting Period management',
            'fiscalyear': 'Fiscal Year management',
        }
        entities = {}

        def _get_entity(module, code, description):
            entity, _ = Entity.objects.get_or_create(
                module=module,
                code=code,
                defaults={
                    'name': code.replace('_', ' ').title(),
                    'description': description,
                    'is_active': True,
                },
            )
            return entity

        for code, description in required_entities.items():
            entities[('accounting', code)] = _get_entity(accounting_module, code, description)

        # Purchasing module entities
        entities[('purchasing', 'purchaseinvoice')] = _get_entity(
            purchasing_module,
            'purchaseinvoice',
            'Purchase invoice management',
        )

        # Ensure custom permissions exist
        def _ensure_permission(definition):
            module = module_map[definition['module']]
            entity = entities[(definition['module'], definition['entity'])]
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

        for definition in SPECIAL_PERMISSION_DEFINITIONS:
            _ensure_permission(definition)

        for definition in JOURNAL_META_PERMISSION_MAP:
            _ensure_permission(definition)

        for definition in PURCHASING_PERMISSION_DEFINITIONS:
            _ensure_permission(definition)

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
            entity=entities[('accounting', 'journal')],
            action__in=['view', 'add', 'change', 'delete'],
            is_active=True,
        ))

        clerk_extra_permissions = set(
            Permission.objects.filter(
            module=accounting_module,
            entity=entities[('accounting', 'journal')],
            action='submit_journal',
        ))

        manager_special_permissions = (
            set(
                Permission.objects.filter(
                    module=accounting_module,
                    entity=entities[('accounting', 'journal')],
                    action__in=['approve_journal', 'reject_journal', 'post_journal', 'reverse_journal'],
                )
            )
            | set(
                Permission.objects.filter(
                    module=accounting_module,
                    entity=entities[('accounting', 'accountingperiod')],
                    action__in=['close_period', 'reopen_period'],
                )
            )
            | set(
                Permission.objects.filter(
                    module=accounting_module,
                    entity=entities[('accounting', 'fiscalyear')],
                    action__in=['close_fiscalyear', 'reopen_fiscalyear'],
                )
            )
        )

        purchasing_view_permissions = set(
            Permission.objects.filter(
                module=purchasing_module,
                entity=entities[('purchasing', 'purchaseinvoice')],
                action='view',
                is_active=True,
            )
        )
        purchasing_edit_permissions = set(
            Permission.objects.filter(
                module=purchasing_module,
                entity=entities[('purchasing', 'purchaseinvoice')],
                action__in=['add', 'change'],
                is_active=True,
            )
        )
        purchasing_delete_permissions = set(
            Permission.objects.filter(
                module=purchasing_module,
                entity=entities[('purchasing', 'purchaseinvoice')],
                action='delete',
                is_active=True,
            )
        )
        purchasing_post_permissions = set(
            Permission.objects.filter(
                module=purchasing_module,
                entity=entities[('purchasing', 'purchaseinvoice')],
                action='post',
                is_active=True,
            )
        )

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
                clerk_permissions = (
                    accounting_view_permissions
                    | journal_crud_permissions
                    | clerk_extra_permissions
                    | purchasing_view_permissions
                    | purchasing_edit_permissions
                )
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
                manager_permissions = (
                    accounting_view_permissions
                    | journal_crud_permissions
                    | clerk_extra_permissions
                    | manager_special_permissions
                    | purchasing_view_permissions
                    | purchasing_edit_permissions
                    | purchasing_post_permissions
                    | purchasing_delete_permissions
                )
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
                auditor_role.permissions.set(auditor_permissions | purchasing_view_permissions)

            self.stdout.write(
                self.style.SUCCESS(
                    f"System roles configured for organization: {org.name}"
                )
            )
