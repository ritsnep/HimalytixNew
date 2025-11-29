# accounting/services/tally_export.py
"""
Tally XML Export Service
Generates Tally-compatible XML for importing invoices, journals, and vouchers
"""
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from django.db.models import QuerySet

from accounting.models import (
    SalesInvoice, PurchaseInvoice, Journal, 
    ChartOfAccount, Customer, Vendor
)


class TallyXMLExporter:
    """Export accounting data to Tally-compatible XML format"""
    
    def __init__(self, company_name: str):
        self.company_name = company_name
    
    def export_sales_invoices(
        self, 
        invoices: QuerySet[SalesInvoice],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Export sales invoices as Tally XML"""
        
        envelope = Element('ENVELOPE')
        
        # Header
        header = SubElement(envelope, 'HEADER')
        SubElement(header, 'TALLYREQUEST').text = 'Import Data'
        
        # Body
        body = SubElement(envelope, 'BODY')
        import_data = SubElement(body, 'IMPORTDATA')
        request_desc = SubElement(import_data, 'REQUESTDESC')
        SubElement(request_desc, 'REPORTNAME').text = 'All Masters'
        
        request_data = SubElement(import_data, 'REQUESTDATA')
        
        # Export each invoice as a voucher
        for invoice in invoices:
            self._add_sales_voucher(request_data, invoice)
        
        return self._prettify_xml(envelope)
    
    def _add_sales_voucher(self, parent: Element, invoice: SalesInvoice):
        """Add a sales invoice as Tally voucher"""
        voucher = SubElement(parent, 'TALLYMESSAGE', xmlns:UDF="TallyUDF")
        voucher_elem = SubElement(voucher, 'VOUCHER', 
                                   REMOTEID=str(invoice.invoice_id),
                                   VCHTYPE="Sales",
                                   ACTION="Create",
                                   OBJVIEW="Invoice Voucher View")
        
        # Basic details
        SubElement(voucher_elem, 'DATE').text = invoice.invoice_date.strftime('%Y%m%d')
        SubElement(voucher_elem, 'VOUCHERTYPENAME').text = 'Sales'
        SubElement(voucher_elem, 'VOUCHERNUMBER').text = invoice.invoice_number
        SubElement(voucher_elem, 'PARTYLEDGERNAME').text = invoice.customer_display_name
        SubElement(voucher_elem, 'PARTYNAME').text = invoice.customer_display_name
        
        # Reference
        SubElement(voucher_elem, 'REFERENCE').text = invoice.reference_number or ''
        
        # Amounts
        SubElement(voucher_elem, 'BASICBASEPARTYNAME').text = invoice.customer_display_name
        
        # Ledger entries (debtor side)
        ledger_entries = SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
        SubElement(ledger_entries, 'LEDGERNAME').text = invoice.customer_display_name
        SubElement(ledger_entries, 'ISDEEMEDPOSITIVE').text = 'Yes'
        SubElement(ledger_entries, 'AMOUNT').text = f"{invoice.total:.2f}"
        
        # Line items (credit side - sales)
        for line in invoice.lines.all():
            line_entry = SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            SubElement(line_entry, 'LEDGERNAME').text = line.revenue_account.account_name
            SubElement(line_entry, 'ISDEEMEDPOSITIVE').text = 'No'
            SubElement(line_entry, 'AMOUNT').text = f"-{line.line_total - line.tax_amount:.2f}"
            
            # Stock item details
            if line.product_code:
                stock_item = SubElement(line_entry, 'INVENTORYALLOCATIONS.LIST')
                SubElement(stock_item, 'STOCKITEMNAME').text = line.product_code
                SubElement(stock_item, 'ACTUALQTY').text = f"{line.quantity:.2f}"
                SubElement(stock_item, 'RATE').text = f"{line.unit_price:.2f}/Unit"
                SubElement(stock_item, 'AMOUNT').text = f"-{line.line_total - line.tax_amount:.2f}"
        
        # VAT entry if applicable
        if invoice.tax_total > 0:
            tax_entry = SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            SubElement(tax_entry, 'LEDGERNAME').text = 'Output VAT 13%'
            SubElement(tax_entry, 'ISDEEMEDPOSITIVE').text = 'No'
            SubElement(tax_entry, 'AMOUNT').text = f"-{invoice.tax_total:.2f}"
    
    def export_journals(
        self,
        journals: QuerySet[Journal],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Export general journals to Tally XML"""
        
        envelope = Element('ENVELOPE')
        header = SubElement(envelope, 'HEADER')
        SubElement(header, 'TALLYREQUEST').text = 'Import Data'
        
        body = SubElement(envelope, 'BODY')
        import_data = SubElement(body, 'IMPORTDATA')
        request_desc = SubElement(import_data, 'REQUESTDESC')
        SubElement(request_desc, 'REPORTNAME').text = 'All Masters'
        
        request_data = SubElement(import_data, 'REQUESTDATA')
        
        for journal in journals:
            self._add_journal_voucher(request_data, journal)
        
        return self._prettify_xml(envelope)
    
    def _add_journal_voucher(self, parent: Element, journal: Journal):
        """Add a journal entry as Tally voucher"""
        voucher = SubElement(parent, 'TALLYMESSAGE', xmlns:UDF="TallyUDF")
        voucher_elem = SubElement(voucher, 'VOUCHER',
                                   REMOTEID=str(journal.journal_id),
                                   VCHTYPE="Journal",
                                   ACTION="Create",
                                   OBJVIEW="Accounting Voucher View")
        
        # Basic details
        SubElement(voucher_elem, 'DATE').text = journal.journal_date.strftime('%Y%m%d')
        SubElement(voucher_elem, 'VOUCHERTYPENAME').text = journal.journal_type.name
        SubElement(voucher_elem, 'VOUCHERNUMBER').text = journal.journal_number
        SubElement(voucher_elem, 'NARRATION').text = journal.description or ''
        
        # Ledger entries
        for line in journal.lines.all():
            ledger_entry = SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            SubElement(ledger_entry, 'LEDGERNAME').text = line.account.account_name
            
            # Debit or Credit
            if line.debit_amount > 0:
                SubElement(ledger_entry, 'ISDEEMEDPOSITIVE').text = 'Yes'
                SubElement(ledger_entry, 'AMOUNT').text = f"{line.debit_amount:.2f}"
            else:
                SubElement(ledger_entry, 'ISDEEMEDPOSITIVE').text = 'No'
                SubElement(ledger_entry, 'AMOUNT').text = f"-{line.credit_amount:.2f}"
            
            # Cost center if applicable
            if line.cost_center:
                category = SubElement(ledger_entry, 'CATEGORYALLOCATIONS.LIST')
                SubElement(category, 'CATEGORY').text = line.cost_center.name
                SubElement(category, 'COSTCENTREALLOCATIONS.LIST')
    
    def export_chart_of_accounts(self, accounts: QuerySet[ChartOfAccount]) -> str:
        """Export chart of accounts to Tally XML for master data sync"""
        
        envelope = Element('ENVELOPE')
        header = SubElement(envelope, 'HEADER')
        SubElement(header, 'TALLYREQUEST').text = 'Import Data'
        
        body = SubElement(envelope, 'BODY')
        import_data = SubElement(body, 'IMPORTDATA')
        request_desc = SubElement(import_data, 'REQUESTDESC')
        SubElement(request_desc, 'REPORTNAME').text = 'All Masters'
        
        request_data = SubElement(import_data, 'REQUESTDATA')
        
        for account in accounts:
            self._add_ledger_master(request_data, account)
        
        return self._prettify_xml(envelope)
    
    def _add_ledger_master(self, parent: Element, account: ChartOfAccount):
        """Add a chart of account as Tally ledger master"""
        message = SubElement(parent, 'TALLYMESSAGE', xmlns:UDF="TallyUDF")
        ledger = SubElement(message, 'LEDGER', NAME=account.account_name, ACTION="Create")
        
        SubElement(ledger, 'NAME').text = account.account_name
        SubElement(ledger, 'PARENT').text = self._map_account_type_to_tally_group(account.account_type)
        SubElement(ledger, 'ISBILLWISEON').text = 'No'
        SubElement(ledger, 'ISCOSTCENTRESON').text = 'No'
        
        # Opening balance
        if account.opening_balance != 0:
            SubElement(ledger, 'OPENINGBALANCE').text = f"{account.opening_balance:.2f}"
    
    def _map_account_type_to_tally_group(self, account_type) -> str:
        """Map Django account types to Tally groups"""
        mapping = {
            'asset': 'Current Assets',
            'liability': 'Current Liabilities',
            'equity': 'Capital Account',
            'income': 'Sales Accounts',
            'expense': 'Direct Expenses'
        }
        return mapping.get(account_type.nature, 'Sundry Debtors')
    
    def _prettify_xml(self, elem: Element) -> str:
        """Return a pretty-printed XML string"""
        rough_string = tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


# Usage in views:
"""
from accounting.services.tally_export import TallyXMLExporter

def export_tally_xml(request):
    organization = request.user.organization
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    invoices = SalesInvoice.objects.filter(
        organization=organization,
        invoice_date__range=[start_date, end_date]
    )
    
    exporter = TallyXMLExporter(organization.name)
    xml_data = exporter.export_sales_invoices(invoices, start_date, end_date)
    
    response = HttpResponse(xml_data, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="tally_export_{start_date}_{end_date}.xml"'
    return response
"""