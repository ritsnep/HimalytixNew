"""
Enhanced Chart of Account views with bulk import and demo data support
"""
from django.views import View
from django.views.generic import CreateView
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.db import transaction
from django.utils.decorators import method_decorator
from django.urls import reverse
import csv
import io
import logging

from accounting.mixins import PermissionRequiredMixin
from accounting.models import ChartOfAccount, AccountType
from accounting.forms import ChartOfAccountForm
from utils.htmx import require_htmx

logger = logging.getLogger(__name__)


class ChartOfAccountBulkCreateView(PermissionRequiredMixin, View):
    """Handle bulk import of chart of accounts from pasted data or CSV"""
    permission_required = ('accounting', 'chartofaccount', 'add')
    
    @method_decorator(require_htmx)
    def post(self, request, *args, **kwargs):
        bulk_data = request.POST.get('bulk_data', '').strip()
        skip_errors = request.POST.get('skip_errors') == 'on'
        update_existing = request.POST.get('update_existing') == 'on'
        validate_only = request.POST.get('validate_only') == 'on'
        
        if not bulk_data:
            return HttpResponse(
                '<div class="alert alert-warning">No data provided. Please paste data from Excel or enter manually.</div>'
            )
        
        organization = self.get_organization()
        if not organization:
            return HttpResponse(
                '<div class="alert alert-danger">No organization found.</div>'
            )
        
        # Parse the bulk data
        results = self._parse_bulk_data(bulk_data, organization)
        
        # Validate accounts
        validated_results = self._validate_accounts(results, organization, update_existing)
        
        # If not validate_only, save the valid accounts
        saved_count = 0
        error_count = 0
        
        if not validate_only:
            with transaction.atomic():
                for result in validated_results:
                    if result['valid']:
                        try:
                            account_data = result['data']
                            if update_existing and result.get('existing'):
                                # Update existing account
                                account = result['existing']
                                for key, value in account_data.items():
                                    setattr(account, key, value)
                                account.save()
                            else:
                                # Create new account
                                ChartOfAccount.objects.create(**account_data)
                            saved_count += 1
                        except Exception as e:
                            logger.error(f"Error saving account: {e}")
                            result['valid'] = False
                            result['errors'].append(str(e))
                            error_count += 1
                            if not skip_errors:
                                raise
                    else:
                        error_count += 1
        
        # Render preview
        context = {
            'results': validated_results,
            'saved_count': saved_count,
            'error_count': error_count,
            'total_count': len(validated_results),
            'validate_only': validate_only,
            'organization': organization,
        }
        
        html = render_to_string('accounting/partials/coa_bulk_preview.html', context, request=request)
        return HttpResponse(html)
    
    def _parse_bulk_data(self, bulk_data, organization):
        """Parse tab-separated or comma-separated data"""
        results = []
        lines = bulk_data.strip().split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Try tab-separated first, then comma
            if '\t' in line:
                parts = [p.strip() for p in line.split('\t')]
            else:
                parts = [p.strip() for p in line.split(',')]
            
            # Ensure we have at least code, name, and type
            while len(parts) < 6:
                parts.append('')
            
            account_code, account_name, account_type, parent_code, description, is_active = parts[:6]
            
            results.append({
                'line_num': line_num,
                'code': account_code,
                'name': account_name,
                'type': account_type.lower(),
                'parent_code': parent_code,
                'description': description,
                'is_active': is_active.lower() in ('true', '1', 'yes', 'active'),
                'organization': organization,
            })
        
        return results
    
    def _validate_accounts(self, results, organization, update_existing):
        """Validate each account"""
        validated = []
        account_types = {at.name.lower(): at for at in AccountType.objects.all()}
        
        for result in results:
            errors = []
            
            # Validate account name
            if not result['name']:
                errors.append('Account name is required')
            
            # Validate account type
            account_type = account_types.get(result['type'])
            if not account_type:
                errors.append(f"Invalid account type: {result['type']}")
            
            # Check for existing account
            existing = None
            if result['code']:
                existing = ChartOfAccount.objects.filter(
                    organization=organization,
                    account_code=result['code']
                ).first()
                
                if existing and not update_existing:
                    errors.append(f"Account code {result['code']} already exists")
            
            # Find parent account
            parent_account = None
            if result['parent_code']:
                parent_account = ChartOfAccount.objects.filter(
                    organization=organization,
                    account_code=result['parent_code']
                ).first()
                
                if not parent_account:
                    errors.append(f"Parent account {result['parent_code']} not found")
            
            # Build account data
            account_data = {
                'organization': organization,
                'account_name': result['name'],
                'account_type': account_type,
                'description': result['description'],
                'is_active': result['is_active'],
                'parent_account': parent_account,
            }
            
            if result['code']:
                account_data['account_code'] = result['code']
            
            validated.append({
                'line_num': result['line_num'],
                'code': result['code'] or 'Auto',
                'name': result['name'],
                'type': result['type'],
                'parent_code': result['parent_code'],
                'valid': len(errors) == 0,
                'errors': errors,
                'data': account_data,
                'existing': existing,
            })
        
        return validated


class ChartOfAccountDemoImportView(PermissionRequiredMixin, View):
    """Import pre-configured demo data templates"""
    permission_required = ('accounting', 'chartofaccount', 'add')
    
    DEMO_TEMPLATES = {
        'basic-business': [
            ('1000', 'Cash', 'asset', '', 'Cash and cash equivalents'),
            ('1010', 'Petty Cash', 'asset', '1000', 'Small cash fund'),
            ('1100', 'Accounts Receivable', 'asset', '', 'Customer receivables'),
            ('1200', 'Inventory', 'asset', '', 'Merchandise inventory'),
            ('1300', 'Prepaid Expenses', 'asset', '', 'Prepaid items'),
            ('1500', 'Fixed Assets', 'asset', '', 'Property, plant & equipment'),
            ('1510', 'Accumulated Depreciation', 'asset', '1500', 'Contra asset account'),
            ('2000', 'Accounts Payable', 'liability', '', 'Vendor payables'),
            ('2100', 'Accrued Expenses', 'liability', '', 'Expenses incurred but not paid'),
            ('2200', 'Unearned Revenue', 'liability', '', 'Advance payments from customers'),
            ('3000', 'Owner\'s Equity', 'equity', '', 'Owner\'s capital'),
            ('3100', 'Retained Earnings', 'equity', '', 'Accumulated profits'),
            ('4000', 'Sales Revenue', 'revenue', '', 'Revenue from sales'),
            ('4100', 'Service Revenue', 'revenue', '', 'Revenue from services'),
            ('5000', 'Cost of Goods Sold', 'expense', '', 'Direct cost of sales'),
            ('5100', 'Salaries Expense', 'expense', '', 'Employee salaries'),
            ('5200', 'Rent Expense', 'expense', '', 'Facility rent'),
            ('5300', 'Utilities Expense', 'expense', '', 'Utilities'),
            ('5400', 'Office Supplies', 'expense', '', 'Office supplies'),
            ('5500', 'Depreciation Expense', 'expense', '', 'Asset depreciation'),
        ],
        'minimal': [
            ('1000', 'Cash', 'asset', '', 'Cash'),
            ('1100', 'Accounts Receivable', 'asset', '', 'Receivables'),
            ('2000', 'Accounts Payable', 'liability', '', 'Payables'),
            ('3000', 'Equity', 'equity', '', 'Owner equity'),
            ('4000', 'Revenue', 'revenue', '', 'Income'),
            ('5000', 'Expenses', 'expense', '', 'Costs'),
        ],
        # Add more templates as needed
    }
    
    @method_decorator(require_htmx)
    def post(self, request, *args, **kwargs):
        template_type = request.POST.get('template_type')
        
        if template_type not in self.DEMO_TEMPLATES:
            return HttpResponse(
                '<div class="alert alert-danger">Invalid template type selected.</div>'
            )
        
        organization = self.get_organization()
        if not organization:
            return HttpResponse(
                '<div class="alert alert-danger">No organization found.</div>'
            )
        
        template_data = self.DEMO_TEMPLATES[template_type]
        account_types = {at.name.lower(): at for at in AccountType.objects.all()}
        
        created_accounts = []
        errors = []
        
        try:
            with transaction.atomic():
                # First pass: create root accounts
                account_map = {}
                for code, name, acc_type, parent_code, description in template_data:
                    if not parent_code:
                        account = ChartOfAccount.objects.create(
                            organization=organization,
                            account_code=code,
                            account_name=name,
                            account_type=account_types.get(acc_type),
                            description=description,
                            is_active=True,
                        )
                        account_map[code] = account
                        created_accounts.append(account)
                
                # Second pass: create child accounts
                for code, name, acc_type, parent_code, description in template_data:
                    if parent_code:
                        parent = account_map.get(parent_code)
                        account = ChartOfAccount.objects.create(
                            organization=organization,
                            account_code=code,
                            account_name=name,
                            account_type=account_types.get(acc_type),
                            parent_account=parent,
                            description=description,
                            is_active=True,
                        )
                        account_map[code] = account
                        created_accounts.append(account)
            
            list_url = reverse('accounting:chart_of_accounts_list')
            html = f'''
            <div class="alert alert-success">
                <h5><i class="bx bx-check-circle"></i> Success!</h5>
                <p>Successfully imported <strong>{len(created_accounts)}</strong> accounts from <strong>{template_type.replace("-", " ").title()}</strong> template.</p>
                <a href="{list_url}" class="btn btn-sm btn-success mt-2">
                    <i class="bx bx-list-ul"></i> View Chart of Accounts
                </a>
            </div>
            '''
            
        except Exception as e:
            logger.error(f"Error importing demo template: {e}")
            html = f'''
            <div class="alert alert-danger">
                <h5><i class="bx bx-error"></i> Error</h5>
                <p>Failed to import template: {str(e)}</p>
            </div>
            '''
        
        return HttpResponse(html)


class ChartOfAccountDemoPreviewView(PermissionRequiredMixin, View):
    """Preview demo template before importing"""
    permission_required = ('accounting', 'chartofaccount', 'view')
    
    @method_decorator(require_htmx)
    def get(self, request, *args, **kwargs):
        template_type = request.GET.get('template')
        
        if template_type not in ChartOfAccountDemoImportView.DEMO_TEMPLATES:
            return HttpResponse('<div class="alert alert-warning">Template not found.</div>')
        
        template_data = ChartOfAccountDemoImportView.DEMO_TEMPLATES.get(template_type, [])
        
        context = {
            'template_type': template_type,
            'template_name': template_type.replace('-', ' ').title(),
            'accounts': template_data,
        }
        
        html = render_to_string('accounting/partials/coa_demo_preview.html', context, request=request)
        return HttpResponse(html)
