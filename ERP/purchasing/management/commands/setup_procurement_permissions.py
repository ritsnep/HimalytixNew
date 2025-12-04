"""
Management command to set up procurement permissions and groups.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from purchasing.models import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine


class Command(BaseCommand):
    help = "Set up procurement permission groups for Purchase Orders and Goods Receipts"

    def handle(self, *args, **options):
        self.stdout.write("Setting up procurement permissions and groups...")

        # Get content types
        po_ct = ContentType.objects.get_for_model(PurchaseOrder)
        pol_ct = ContentType.objects.get_for_model(PurchaseOrderLine)
        gr_ct = ContentType.objects.get_for_model(GoodsReceipt)
        grl_ct = ContentType.objects.get_for_model(GoodsReceiptLine)

        # Define permission mapping
        permission_codenames = {
            "view_purchaseorder": (po_ct, "Can view purchase order"),
            "add_purchaseorder": (po_ct, "Can add purchase order"),
            "change_purchaseorder": (po_ct, "Can change purchase order"),
            "delete_purchaseorder": (po_ct, "Can delete purchase order"),
            "view_purchaseorderline": (pol_ct, "Can view purchase order line"),
            "add_purchaseorderline": (pol_ct, "Can add purchase order line"),
            "change_purchaseorderline": (pol_ct, "Can change purchase order line"),
            "delete_purchaseorderline": (pol_ct, "Can delete purchase order line"),
            "view_goodsreceipt": (gr_ct, "Can view goods receipt"),
            "add_goodsreceipt": (gr_ct, "Can add goods receipt"),
            "change_goodsreceipt": (gr_ct, "Can change goods receipt"),
            "delete_goodsreceipt": (gr_ct, "Can delete goods receipt"),
            "view_goodsreceiptline": (grl_ct, "Can view goods receipt line"),
            "add_goodsreceiptline": (grl_ct, "Can add goods receipt line"),
            "change_goodsreceiptline": (grl_ct, "Can change goods receipt line"),
            "delete_goodsreceiptline": (grl_ct, "Can delete goods receipt line"),
        }

        # Create/update permissions
        permissions = {}
        for codename, (content_type, description) in permission_codenames.items():
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": description}
            )
            permissions[codename] = perm
            if created:
                self.stdout.write(f"[+] Created permission: {codename}")
            else:
                self.stdout.write(f"[*] Permission exists: {codename}")

        # Create groups
        groups = {
            "Procurement Manager": [
                "view_purchaseorder", "add_purchaseorder", "change_purchaseorder", "delete_purchaseorder",
                "view_purchaseorderline", "add_purchaseorderline", "change_purchaseorderline", "delete_purchaseorderline",
                "view_goodsreceipt", "add_goodsreceipt", "change_goodsreceipt", "delete_goodsreceipt",
                "view_goodsreceiptline", "add_goodsreceiptline", "change_goodsreceiptline", "delete_goodsreceiptline",
            ],
            "Warehouse Manager": [
                "view_purchaseorder",
                "view_purchaseorderline",
                "view_goodsreceipt", "add_goodsreceipt", "change_goodsreceipt",
                "view_goodsreceiptline", "add_goodsreceiptline", "change_goodsreceiptline",
            ],
            "Finance Manager": [
                "view_purchaseorder",
                "view_purchaseorderline",
                "view_goodsreceipt",
                "view_goodsreceiptline",
            ],
        }

        for group_name, perm_codenames in groups.items():
            group, created = Group.objects.get_or_create(name=group_name)
            
            # Add permissions to group
            for codename in perm_codenames:
                if codename in permissions:
                    group.permissions.add(permissions[codename])
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"[+] Created group: {group_name}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"[*] Group exists: {group_name}"))

        self.stdout.write(self.style.SUCCESS("\n[OK] Procurement permissions and groups setup complete!"))
