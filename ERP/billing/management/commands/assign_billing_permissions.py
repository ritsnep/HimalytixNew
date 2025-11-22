from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission

ROLE_PERMS = {
    "Administrator": [
        "add_invoiceheader",
        "view_invoiceheader",
        "change_invoiceheader",
        "add_invoiceline",
        "view_invoiceline",
        "view_invoiceauditlog",
        "add_creditdebitnote",
        "view_creditdebitnote",
    ],
    "User": [
        "add_invoiceheader",
        "view_invoiceheader",
        "add_invoiceline",
        "view_invoiceline",
        "view_creditdebitnote",
    ],
}


class Command(BaseCommand):
    help = "Assign billing permissions to roles (groups) by name."

    def handle(self, *args, **options):
        from django.contrib.auth.models import Group

        for group_name, codenames in ROLE_PERMS.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            perms = Permission.objects.filter(codename__in=codenames)
            group.permissions.add(*perms)
            self.stdout.write(self.style.SUCCESS(f"Updated {group_name} with {perms.count()} billing permissions."))
