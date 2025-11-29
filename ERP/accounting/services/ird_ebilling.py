# accounting/services/ird_ebilling.py
"""
Nepal IRD E-Billing Integration Service
Handles real-time invoice submission, QR code generation, and fiscal year management
"""
import hashlib
import hmac
import json
import qrcode
from io import BytesIO
from decimal import Decimal
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from accounting.models import SalesInvoice, FiscalYear, Organization


class IRDConfig:
    """IRD API Configuration"""
    # Get from settings or environment
    API_BASE_URL = getattr(settings, 'IRD_API_URL', 'https://ird.gov.np/api/v1')
    USERNAME = getattr(settings, 'IRD_USERNAME', '')
    PASSWORD = getattr(settings, 'IRD_PASSWORD', '')
    SELLER_PAN = getattr(settings, 'IRD_SELLER_PAN', '')
    
    # IRD requires fiscal year in Bikram Sambat format (e.g., "2080/81")
    @staticmethod
    def get_fiscal_year_code(invoice_date: date) -> str:
        """Convert Gregorian date to Bikram Sambat fiscal year"""
        # Nepal fiscal year: mid-July to mid-July
        # Simplified conversion (you'd use a proper BS calendar library)
        year = invoice_date.year
        month = invoice_date.month
        
        # If before mid-July (Shrawan 1), use previous year
        if month < 7 or (month == 7 and invoice_date.day < 16):
            bs_year = year + 56  # Approximate conversion
            return f"{bs_year}/{str(bs_year + 1)[-2:]}"
        else:
            bs_year = year + 57
            return f"{bs_year}/{str(bs_year + 1)[-2:]}"


class IRDEBillingService:
    """Main service for IRD e-billing integration"""
    
    def __init__(self, organization: Organization):
        self.organization = organization
        self.config = IRDConfig()
        self.session = requests.Session()
    
    def submit_invoice(self, invoice: SalesInvoice) -> Dict:
        """
        Submit sales invoice to IRD in real-time
        Returns: {'success': bool, 'ird_signature': str, 'qr_data': str}
        """
        if invoice.ird_status == 'synced':
            return {
                'success': False,
                'error': 'Invoice already submitted to IRD'
            }
        
        try:
            # Prepare IRD payload
            payload = self._prepare_invoice_payload(invoice)
            
            # Submit to IRD
            response = self._call_ird_api('/invoice/submit', payload)
            
            if response.get('status') == 'success':
                # Generate QR code
                qr_data = self._generate_qr_data(invoice, response)
                
                # Update invoice with IRD data
                with transaction.atomic():
                    invoice.ird_signature = response.get('signature')
                    invoice.ird_ack_id = response.get('acknowledgment_id')
                    invoice.ird_status = 'synced'
                    invoice.ird_last_response = response
                    invoice.ird_last_submitted_at = timezone.now()
                    invoice.save(update_fields=[
                        'ird_signature',
                        'ird_ack_id', 
                        'ird_status',
                        'ird_last_response',
                        'ird_last_submitted_at'
                    ])
                
                return {
                    'success': True,
                    'ird_signature': response.get('signature'),
                    'qr_data': qr_data,
                    'ack_id': response.get('acknowledgment_id')
                }
            else:
                # Log failure
                invoice.ird_status = 'failed'
                invoice.ird_last_response = response
                invoice.save(update_fields=['ird_status', 'ird_last_response'])
                
                return {
                    'success': False,
                    'error': response.get('message', 'IRD submission failed')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Exception during IRD submission: {str(e)}'
            }
    
    def _prepare_invoice_payload(self, invoice: SalesInvoice) -> Dict:
        """Prepare invoice data in IRD-compliant format"""
        # Get fiscal year in BS format
        fiscal_year = self.config.get_fiscal_year_code(invoice.invoice_date)
        
        # Prepare line items
        items = []
        for line in invoice.lines.all():
            items.append({
                'description': line.description,
                'quantity': float(line.quantity),
                'unit_price': float(line.unit_price),
                'amount': float(line.line_total - line.tax_amount),
                'vat_amount': float(line.tax_amount),
                'total_amount': float(line.line_total)
            })
        
        # Main payload structure
        payload = {
            'username': self.config.USERNAME,
            'password': self.config.PASSWORD,
            'seller_pan': self.config.SELLER_PAN,
            'buyer_pan': invoice.customer.tax_id if invoice.customer else '',
            'buyer_name': invoice.customer_display_name,
            'fiscal_year': fiscal_year,
            'invoice_number': invoice.invoice_number,
            'invoice_date': invoice.invoice_date.strftime('%Y.%m.%d'),
            'total_sales': float(invoice.subtotal),
            'taxable_amount': float(invoice.subtotal),
            'tax_amount': float(invoice.tax_total),
            'total_amount': float(invoice.total),
            'payment_method': 'CASH',  # or from invoice.payment_method
            'vat_refund_amount': 0,
            'transaction_id': str(invoice.invoice_id),
            'items': items,
            'is_realtime': True
        }
        
        return payload
    
    def _call_ird_api(self, endpoint: str, payload: Dict) -> Dict:
        """Make API call to IRD server"""
        url = f"{self.config.API_BASE_URL}{endpoint}"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            return {
                'status': 'error',
                'message': 'IRD API timeout - please try again'
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f'IRD API error: {str(e)}'
            }
    
    def _generate_qr_data(self, invoice: SalesInvoice, ird_response: Dict) -> str:
        """
        Generate QR code data string for invoice
        Format: IRD_ACK_ID,INVOICE_NO,DATE,AMOUNT,SIGNATURE
        """
        qr_string = (
            f"{ird_response.get('acknowledgment_id')},"
            f"{invoice.invoice_number},"
            f"{invoice.invoice_date.strftime('%Y-%m-%d')},"
            f"{invoice.total},"
            f"{ird_response.get('signature')}"
        )
        return qr_string
    
    def generate_qr_code_image(self, qr_data: str) -> BytesIO:
        """Generate QR code image from data string"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    
    def cancel_invoice(self, invoice: SalesInvoice, reason: str) -> Dict:
        """Cancel an invoice in IRD system"""
        if invoice.ird_status != 'synced':
            return {
                'success': False,
                'error': 'Invoice not submitted to IRD'
            }
        
        payload = {
            'username': self.config.USERNAME,
            'password': self.config.PASSWORD,
            'invoice_number': invoice.invoice_number,
            'ack_id': invoice.ird_ack_id,
            'reason': reason
        }
        
        response = self._call_ird_api('/invoice/cancel', payload)
        
        if response.get('status') == 'success':
            invoice.status = 'cancelled'
            invoice.ird_status = 'cancelled'
            invoice.save(update_fields=['status', 'ird_status'])
            
            return {'success': True}
        else:
            return {
                'success': False,
                'error': response.get('message', 'Cancellation failed')
            }
    
    def print_invoice(self, invoice: SalesInvoice) -> Dict:
        """
        Log invoice print/reprint to IRD
        IRD requires tracking of reprints for audit purposes
        """
        invoice.ird_reprint_count += 1
        invoice.ird_last_printed_at = timezone.now()
        invoice.save(update_fields=[
            'ird_reprint_count',
            'ird_last_printed_at'
        ])
        
        # Notify IRD about reprint (if count > 1)
        if invoice.ird_reprint_count > 1:
            payload = {
                'username': self.config.USERNAME,
                'invoice_number': invoice.invoice_number,
                'ack_id': invoice.ird_ack_id,
                'reprint_count': invoice.ird_reprint_count
            }
            self._call_ird_api('/invoice/reprint', payload)
        
        return {
            'success': True,
            'reprint_count': invoice.ird_reprint_count
        }
# Usage in views:
"""
from accounting.services.ird_ebilling import IRDEBillingService

# When creating/posting invoice
def post_sales_invoice(request, invoice_id):
    invoice = get_object_or_404(SalesInvoice, pk=invoice_id)
    organization = request.user.organization
    
    # Submit to IRD
    ird_service = IRDEBillingService(organization)
    result = ird_service.submit_invoice(invoice)
    
    if result['success']:
        messages.success(request, f"Invoice submitted to IRD. Ack ID: {result['ack_id']}")
        # Generate QR code for printing
        qr_image = ird_service.generate_qr_code_image(result['qr_data'])
    else:
        messages.error(request, f"IRD submission failed: {result['error']}")
"""