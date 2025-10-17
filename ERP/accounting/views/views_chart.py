from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
import json
from accounting.models import ChartOfAccount, AccountType
from django.db.models import Prefetch

def build_account_tree(accounts, parent_id=None):
    tree = []
    for acc in [a for a in accounts if (a['parent_account_id'] == parent_id)]:
        children = build_account_tree(accounts, acc['account_id'])
        tree.append({
            'id': acc['account_id'],
            'name': acc['account_name'],
            'code': acc['account_code'],
            'type': acc['account_type__nature'],
            'account_type': acc['account_type__name'],
            'children': children,
        })
    return tree

class ChartOfAccountTreeListView(View):
    def get(self, request):
        return render(request, "accounting/chart_of_accounts_tree.html")

class ChartOfAccountTreeAPI(View):
    def get(self, request):
        org = request.user.get_active_organization()
        qs = ChartOfAccount.objects.filter(organization=org, is_archived=False)
        qs = qs.select_related('account_type').order_by('display_order', 'account_code')
        accounts = list(qs.values(
            'account_id', 'account_name', 'account_code', 'parent_account_id',
            'account_type__nature', 'account_type__name', 'display_order'
        ))
        tree = build_account_tree(accounts)
        return JsonResponse({'tree': tree})
class ChartOfAccountQuickCreate(View):
    def post(self, request):
        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

        org = request.user.get_active_organization()
        if not org:
            return JsonResponse({"success": False, "error": "Organization required"}, status=400)

        name = payload.get("name", "").strip()
        nature = payload.get("type")
        parent_id = payload.get("parent_id")
        code = payload.get("code") or None
        if not name:
            return JsonResponse({"success": False, "error": "Name required"}, status=400)
        try:
            acc_type = AccountType.objects.filter(nature=nature).first()
            if not acc_type:
                return JsonResponse({"success": False, "error": "Invalid account type"}, status=400)
            parent = None
            if parent_id:
                parent = ChartOfAccount.objects.get(pk=parent_id, organization=org)
            account = ChartOfAccount.objects.create(
                organization=org,
                parent_account=parent,
                account_type=acc_type,
                account_code=code or "",
                account_name=name,
                created_by=getattr(request, "user", None),
            )
            return JsonResponse({"success": True, "account_id": account.account_id})
        except ChartOfAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Parent not found"}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

class ChartOfAccountValidateHierarchy(View):
    def get(self, request):
        org = request.user.get_active_organization()
        qs = ChartOfAccount.objects.filter(organization=org).select_related("parent_account")
        errors = []
        for acc in qs:
            parent = acc.parent_account
            visited = set([acc.account_id])
            depth = 1
            while parent:
                if parent.organization_id != acc.organization_id:
                    errors.append(
                        f"{acc.account_code} parent belongs to different organization"
                    )
                    break
                if parent.account_id in visited:
                    errors.append(
                        f"Circular reference involving {acc.account_code}"
                    )
                    break
                visited.add(parent.account_id)
                parent = parent.parent_account
                depth += 1
                if depth > 10:
                    errors.append(f"Hierarchy too deep at {acc.account_code}")
                    break
        return JsonResponse({"valid": not errors, "errors": errors})