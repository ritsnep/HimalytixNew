import json
from django.http import JsonResponse
from django.views import View
from ..forms_factory import VOUCHER_FORMS
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class ValidateFieldView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            voucher_type = data.get('voucher_type')
            field_name = data.get('field_name')
            field_value = data.get('field_value')
            
            if not all([voucher_type, field_name, field_value]):
                return JsonResponse({'status': 'error', 'message': 'Missing required data'}, status=400)

            form_class = VOUCHER_FORMS.get(voucher_type)
            if not form_class:
                return JsonResponse({'status': 'error', 'message': 'Invalid voucher type'}, status=400)

            form = form_class(data={field_name: field_value})
            if form.is_valid():
                return JsonResponse({'status': 'success', 'errors': {}})
            else:
                return JsonResponse({'status': 'error', 'errors': form.errors})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)