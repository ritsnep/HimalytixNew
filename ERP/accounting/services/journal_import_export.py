import pandas as pd
from django.http import HttpResponse
from openpyxl import Workbook
from accounting.models import Journal

class JournalExportService:
    def export_to_excel(self, queryset):
        wb = Workbook()
        ws = wb.active
        
        # Headers
        headers = ['Date', 'Number', 'Description', 'Account', 'Debit', 'Credit']
        ws.append(headers)
        
        # Data
        for journal in queryset:
            for line in journal.lines.all():
                ws.append([
                    journal.date,
                    journal.number,
                    journal.description,
                    line.account.code,
                    line.debit,
                    line.credit
                ])
        
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="journal_export.xlsx"'
        wb.save(response)
        return response