import csv
import io
import openpyxl
from django.http import HttpResponse
from django.utils import timezone
from inventory.models import Product
from accounting.models import Customer, SalesInvoice

class ExportService:
    @staticmethod
    def export_dataset(dataset, queryset, fmt='csv'):
        """
        Export a queryset to a file-like object in the specified format.
        Returns (buffer, filename, content_type)
        """
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{dataset}_{timestamp}.{fmt}"
        
        if fmt == 'csv':
            buffer = io.StringIO()
            content_type = 'text/csv'
            writer = csv.writer(buffer)
            ExportService._write_data(dataset, queryset, writer)
            buffer.seek(0)
            # For CSV, we need bytes for HttpResponse if we want to be consistent, 
            # but StringIO is text. HttpResponse handles string content fine.
            # However, if we want to return bytes, we should encode.
            # Let's return the buffer as is, the view will handle it.
            return buffer, filename, content_type
            
        elif fmt == 'xlsx':
            buffer = io.BytesIO()
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = dataset.capitalize()
            
            # Adapter for openpyxl to look like csv writer
            class ExcelWriter:
                def __init__(self, sheet):
                    self.sheet = sheet
                def writerow(self, row):
                    self.sheet.append(row)
            
            writer = ExcelWriter(sheet)
            ExportService._write_data(dataset, queryset, writer)
            workbook.save(buffer)
            buffer.seek(0)
            return buffer, filename, content_type
        
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    @staticmethod
    def _write_data(dataset, queryset, writer):
        if dataset == 'products':
            headers = ['Code', 'Name', 'Category', 'Unit', 'Price', 'Cost', 'Stock']
            writer.writerow(headers)
            for item in queryset:
                writer.writerow([
                    item.code,
                    item.name,
                    str(item.category) if item.category else '',
                    str(item.unit) if item.unit else '',
                    item.sale_price,
                    item.cost_price,
                    item.current_stock
                ])
                
        elif dataset == 'customers':
            headers = ['Name', 'Email', 'Phone', 'Address', 'Tax ID', 'Balance']
            writer.writerow(headers)
            for item in queryset:
                writer.writerow([
                    item.name,
                    item.email,
                    item.phone,
                    item.address,
                    item.tax_id,
                    item.current_balance
                ])
                
        elif dataset == 'invoices':
            headers = ['Invoice #', 'Date', 'Customer', 'Total', 'Status', 'Due Date']
            writer.writerow(headers)
            for item in queryset:
                writer.writerow([
                    item.invoice_number,
                    item.date,
                    item.customer_name,
                    item.total_amount,
                    item.status,
                    item.due_date
                ])
        
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
