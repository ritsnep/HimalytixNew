from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from accounting.settings_loader import load_settings, save_settings, get_audit_trail, preview_diff, rollback_settings, validate_settings

class VoucherSettingsView(View):
    def get(self, request):
        settings = load_settings()
        return render(request, "accounting/voucher_settings.html", {"settings": settings, "audit": get_audit_trail()})

    def post(self, request):
        new_settings = request.POST.get("settings_json")
        valid, errors = validate_settings(new_settings)
        if not valid:
            return JsonResponse({"success": False, "errors": errors})
        save_settings(new_settings, user=request.user)
        return JsonResponse({"success": True})

class VoucherSettingsDiffView(View):
    def post(self, request):
        new_settings = request.POST.get("settings_json")
        diff = preview_diff(new_settings)
        return JsonResponse({"diff": diff})

class VoucherSettingsRollbackView(View):
    def post(self, request):
        rollback_settings()
        return JsonResponse({"success": True})
