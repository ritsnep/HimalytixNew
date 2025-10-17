from decimal import Decimal, InvalidOperation
import pandas as pd
from typing import List, Dict, Any
from django.db import transaction
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from accounting.models import (
    Journal, JournalLine, ChartOfAccount as Account, Currency, JournalType,
    FiscalYear, AccountingPeriod, CostCenter, Department, Project
)
from accounting.utils.helpers import get_current_fiscal_year_and_period
from accounting.services.journal_entry_service import JournalEntryService
import logging
import uuid

logger = logging.getLogger(__name__)

class JournalImportService:
    """
    Service for handling the import of journal entries from a spreadsheet.
    """
    EXPECTED_COLUMNS = [
        'grouping_key', 'journal_date', 'journal_type_code', 'journal_reference',
        'journal_description', 'currency_code', 'exchange_rate', 'account_code',
        'line_description', 'debit_amount', 'credit_amount', 'department_code',
        'project_code', 'cost_center_code'
    ]

    def __init__(self, organization, user):
        self.organization = organization
        self.user = user
        self.errors = []
        self.data_frame = None

    def _read_file(self, file):
        """Reads the uploaded file into a pandas DataFrame."""
        try:
            if file.name.endswith('.csv'):
                self.data_frame = pd.read_csv(file)
            elif file.name.endswith(('.xls', '.xlsx')):
                self.data_frame = pd.read_excel(file)
            else:
                self.errors.append({'row': 'File', 'message': _('Unsupported file format.')})
                return False
            
            # Standardize column names
            self.data_frame.columns = [col.strip().lower() for col in self.data_frame.columns]
            return True
        except Exception as e:
            logger.error(f"Error reading import file: {e}")
            self.errors.append({'row': 'File', 'message': _('Could not read the file.')})
            return False

    def _validate_columns(self):
        """Validates that all expected columns are present in the DataFrame."""
        missing_cols = [col for col in self.EXPECTED_COLUMNS if col not in self.data_frame.columns]
        if missing_cols:
            self.errors.append({'row': 'File', 'message': _('Missing columns: {}').format(', '.join(missing_cols))})
            return False
        return True

    def _prefetch_data(self):
        """Prefetches related data from the database for performance."""
        account_codes = self.data_frame['account_code'].dropna().unique()
        journal_type_codes = self.data_frame['journal_type_code'].dropna().unique()
        currency_codes = self.data_frame['currency_code'].dropna().unique()
        department_codes = self.data_frame['department_code'].dropna().unique()
        project_codes = self.data_frame['project_code'].dropna().unique()
        cost_center_codes = self.data_frame['cost_center_code'].dropna().unique()

        self.accounts = {a.code: a for a in Account.objects.filter(code__in=account_codes, organization=self.organization)}
        self.journal_types = {jt.code: jt for jt in JournalType.objects.filter(code__in=journal_type_codes, organization=self.organization)}
        self.currencies = {c.currency_code: c for c in Currency.objects.filter(currency_code__in=currency_codes)}
        self.departments = {d.code: d for d in Department.objects.filter(code__in=department_codes, organization=self.organization)}
        self.projects = {p.code: p for p in Project.objects.filter(code__in=project_codes, organization=self.organization)}
        self.cost_centers = {cc.code: cc for cc in CostCenter.objects.filter(code__in=cost_center_codes, organization=self.organization)}

    def validate_and_cache(self, file):
        """
        Reads, validates the data, and caches it for final import.
        Returns a dictionary with validation results.
        """
        if not self._read_file(file) or not self._validate_columns():
            return {'is_valid': False, 'errors': self.errors, 'file_key': None}

        self._prefetch_data()

        grouped_data = self.data_frame.groupby('grouping_key')
        for group_key, group_df in grouped_data:
            self._validate_group(group_key, group_df)

        if self.errors:
            return {'is_valid': False, 'errors': self.errors, 'file_key': None}

        file_key = f"import_{uuid.uuid4()}"
        cache.set(file_key, self.data_frame.to_dict('records'), timeout=3600) # Cache for 1 hour
        
        return {'is_valid': True, 'errors': [], 'file_key': file_key}

    def _validate_group(self, group_key, group_df):
        """Validates a single journal entry group."""
        first_row = group_df.iloc[0]
        
        # Header-level validations
        self._validate_date(group_key, first_row)
        self._validate_journal_type(group_key, first_row)
        self._validate_currency(group_key, first_row)
        
        # Line-level validations
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')

        for index, row in group_df.iterrows():
            row_num = index + 2  # For user-friendly row numbers
            self._validate_account(group_key, row, row_num)
            debit, credit = self._validate_amounts(group_key, row, row_num)
            total_debit += debit
            total_credit += credit
        
        if total_debit != total_credit:
            self.errors.append({'row': f'Group {group_key}', 'message': _('Journal must balance. Debits: {}, Credits: {}').format(total_debit, total_credit)})

    def _validate_date(self, key, row):
        date_str = str(row.get('journal_date'))
        try:
            journal_date = pd.to_datetime(date_str).date()
            _, period = get_current_fiscal_year_and_period(self.organization, journal_date)
            if not period or not period.is_open:
                self.errors.append({'row': f'Group {key}', 'message': _('No open accounting period for date {}').format(journal_date)})
        except (ValueError, TypeError):
            self.errors.append({'row': f'Group {key}', 'message': _('Invalid date format for {}. Expected YYYY-MM-DD.').format(date_str)})

    def _validate_journal_type(self, key, row):
        code = row.get('journal_type_code')
        if code not in self.journal_types:
            self.errors.append({'row': f'Group {key}', 'message': _('Journal Type "{}" not found.').format(code)})

    def _validate_currency(self, key, row):
        code = row.get('currency_code')
        if code not in self.currencies:
            self.errors.append({'row': f'Group {key}', 'message': _('Currency "{}" not found.').format(code)})

    def _validate_account(self, key, row, row_num):
        code = row.get('account_code')
        if code not in self.accounts:
            self.errors.append({'row': row_num, 'message': _('Account "{}" not found.').format(code)})

    def _validate_amounts(self, key, row, row_num):
        try:
            debit = Decimal(row.get('debit_amount', '0.00') or '0.00')
            credit = Decimal(row.get('credit_amount', '0.00') or '0.00')
            if debit < 0 or credit < 0:
                self.errors.append({'row': row_num, 'message': _('Amounts cannot be negative.')})
            if debit > 0 and credit > 0:
                self.errors.append({'row': row_num, 'message': _('Line cannot have both debit and credit.')})
            return debit, credit
        except InvalidOperation:
            self.errors.append({'row': row_num, 'message': _('Invalid amount format.')})
            return Decimal('0'), Decimal('0')

    def commit_import(self, file_key):
        """
        Creates journal entries from the cached data.
        """
        cached_data = cache.get(file_key)
        if not cached_data:
            return {'created_journals': 0, 'created_lines': 0, 'error': _('Import data expired or not found.')}

        self.data_frame = pd.DataFrame.from_records(cached_data)
        self._prefetch_data() # Re-fetch data to be safe

        journals_to_create = []
        lines_to_create = []
        
        grouped_data = self.data_frame.groupby('grouping_key')

        with transaction.atomic():
            journal_entry_service = JournalEntryService(self.user, self.organization)
            created_journals_count = 0
            created_lines_count = 0

            for group_key, group_df in grouped_data:
                first_row = group_df.iloc[0].to_dict()
                journal_date = pd.to_datetime(first_row['journal_date']).date()
                
                journal_data = {
                    'journal_date': journal_date,
                    'journal_type': self.journal_types[first_row['journal_type_code']],
                    'reference': first_row.get('journal_reference', ''),
                    'description': first_row.get('journal_description', ''),
                    'currency_code': self.currencies[first_row['currency_code']].currency_code,
                    'exchange_rate': Decimal(first_row.get('exchange_rate', '1.0')),
                    'status': 'draft'
                }

                lines_data = []
                for _, row_data in group_df.iterrows():
                    row = row_data.to_dict()
                    lines_data.append({
                        'account': self.accounts[row['account_code']],
                        'description': row.get('line_description', ''),
                        'debit_amount': Decimal(row.get('debit_amount', '0.00') or '0.00'),
                        'credit_amount': Decimal(row.get('credit_amount', '0.00') or '0.00'),
                        'department': self.departments.get(row.get('department_code')),
                        'project': self.projects.get(row.get('project_code')),
                        'cost_center': self.cost_centers.get(row.get('cost_center_code')),
                    })
                
                try:
                    journal_entry_service.create_journal_entry(journal_data, lines_data)
                    created_journals_count += 1
                    created_lines_count += len(lines_data)
                except ValueError as e:
                    return {'created_journals': 0, 'created_lines': 0, 'error': str(e)}

            cache.delete(file_key)

        return {
            'created_journals': created_journals_count,
            'created_lines': created_lines_count,
            'error': None
        }

def import_journal_entries(file_path: str, organization_id: int) -> Dict[str, Any]:
    """
    Import journal entries from an Excel file
    
    Args:
        file_path (str): Path to the Excel file
        organization_id (int): ID of the organization
        
    Returns:
        Dict containing status and results/errors
    """
    try:
        df = pd.read_excel(file_path)
        
        # Validate required columns
        required_columns = ['journal_date', 'reference', 'description', 'account_code', 
                          'debit_amount', 'credit_amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return {
                'success': False,
                'errors': f"Missing required columns: {', '.join(missing_columns)}"
            }

        # Process the data
        journals_to_create = []
        current_journal = None
        
        for _, row in df.iterrows():
            # Start a new journal entry if reference changes
            if current_journal is None or current_journal['reference'] != row['reference']:
                if current_journal:
                    journals_to_create.append(current_journal)
                
                current_journal = {
                    'reference': row['reference'],
                    'journal_date': row['journal_date'],
                    'description': row['description'],
                    'lines': []
                }
            
            # Add journal line
            current_journal['lines'].append({
                'account_code': row['account_code'],
                'debit_amount': row['debit_amount'] or 0,
                'credit_amount': row['credit_amount'] or 0,
                'description': row.get('line_description', '')
            })
        
        if current_journal:
            journals_to_create.append(current_journal)

        # Save to database
        with transaction.atomic():
            for journal_data in journals_to_create:
                journal = Journal.objects.create(
                    organization_id=organization_id,
                    journal_date=journal_data['journal_date'],
                    reference=journal_data['reference'],
                    description=journal_data['description'],
                    status='draft'
                )
                
                for line in journal_data['lines']:
                    account = Account.objects.get(
                        organization_id=organization_id,
                        account_code=line['account_code']
                    )
                    
                    JournalLine.objects.create(
                        journal=journal,
                        account=account,
                        debit_amount=line['debit_amount'],
                        credit_amount=line['credit_amount'],
                        description=line['description']
                    )
                
                journal.update_totals()

        return {
            'success': True,
            'message': f'Successfully imported {len(journals_to_create)} journal entries'
        }

    except Exception as e:
        return {
            'success': False,
            'errors': str(e)
        }