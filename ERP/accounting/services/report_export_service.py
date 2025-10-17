"""
Report Export Service - Phase 3 Task 2

Handles exporting reports to multiple formats:
- PDF (via WeasyPrint or ReportLab)
- Excel (via openpyxl)
- CSV (via csv module)
"""

from io import BytesIO, StringIO
import csv
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class ReportExportService:
    """
    Service for exporting financial reports to various formats.
    
    Supports:
    - CSV format (streamable, lightweight)
    - Excel format (formatted, with calculations)
    - PDF format (print-ready, styled)
    """
    
    @staticmethod
    def to_csv(report_data: Dict[str, Any]) -> Tuple[BytesIO, str]:
        """
        Export report to CSV format.
        
        Args:
            report_data: Report data dictionary from ReportService
            
        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        logger.info(f"Exporting report to CSV: {report_data.get('report_type')}")
        
        output = StringIO()
        writer = csv.writer(output)
        
        report_type = report_data.get('report_type')
        
        # Write header
        writer.writerow([f"{report_data.get('report_type', 'Report').upper()} REPORT"])
        writer.writerow([f"Organization: {report_data.get('organization')}"])
        if 'as_of_date' in report_data:
            writer.writerow([f"As of: {report_data['as_of_date']}"])
        elif 'period' in report_data:
            writer.writerow([f"Period: {report_data['period']}"])
        writer.writerow([f"Generated: {report_data['generated_at']}"])
        writer.writerow([])  # Blank line
        
        # Write data based on report type
        if report_type == 'general_ledger':
            ReportExportService._export_ledger_csv(writer, report_data)
        elif report_type == 'trial_balance':
            ReportExportService._export_trial_balance_csv(writer, report_data)
        elif report_type == 'profit_loss':
            ReportExportService._export_pl_csv(writer, report_data)
        elif report_type == 'balance_sheet':
            ReportExportService._export_bs_csv(writer, report_data)
        elif report_type == 'cash_flow':
            ReportExportService._export_cf_csv(writer, report_data)
        elif report_type == 'ar_aging':
            ReportExportService._export_ar_aging_csv(writer, report_data)
        
        # Convert to bytes
        csv_bytes = BytesIO(output.getvalue().encode('utf-8'))
        filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return csv_bytes, filename
    
    @staticmethod
    def to_excel(report_data: Dict[str, Any]) -> Tuple[BytesIO, str]:
        """
        Export report to Excel format.
        
        Requires: openpyxl package
        
        Args:
            report_data: Report data dictionary
            
        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        logger.info(f"Exporting report to Excel: {report_data.get('report_type')}")
        
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            logger.error("openpyxl not installed. Install with: pip install openpyxl")
            raise ImportError("openpyxl is required for Excel export")
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        
        # Define styles
        title_font = Font(bold=True, size=14)
        header_font = Font(bold=True, size=11)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font_white = Font(bold=True, color="FFFFFF")
        total_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        total_font = Font(bold=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Write header
        row = 1
        ws.cell(row, 1, f"{report_data.get('report_type', 'Report').upper()} REPORT")
        ws.cell(row, 1).font = title_font
        row += 1
        
        ws.cell(row, 1, f"Organization: {report_data.get('organization')}")
        row += 1
        
        if 'as_of_date' in report_data:
            ws.cell(row, 1, f"As of: {report_data['as_of_date']}")
        elif 'period' in report_data:
            ws.cell(row, 1, f"Period: {report_data['period']}")
        row += 1
        
        ws.cell(row, 1, f"Generated: {report_data['generated_at']}")
        row += 2
        
        # Write report data based on type
        report_type = report_data.get('report_type')
        if report_type == 'general_ledger':
            row = ReportExportService._export_ledger_excel(ws, report_data, row, header_fill, header_font_white, border, total_fill, total_font)
        elif report_type == 'trial_balance':
            row = ReportExportService._export_trial_balance_excel(ws, report_data, row, header_fill, header_font_white, border, total_fill, total_font)
        elif report_type == 'profit_loss':
            row = ReportExportService._export_pl_excel(ws, report_data, row, header_fill, header_font_white, border, total_fill, total_font)
        elif report_type == 'balance_sheet':
            row = ReportExportService._export_bs_excel(ws, report_data, row, header_fill, header_font_white, border, total_fill, total_font)
        elif report_type == 'cash_flow':
            row = ReportExportService._export_cf_excel(ws, report_data, row, header_fill, header_font_white, border, total_fill, total_font)
        elif report_type == 'ar_aging':
            row = ReportExportService._export_ar_aging_excel(ws, report_data, row, header_fill, header_font_white, border, total_fill, total_font)
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 15
        
        # Save to bytes
        excel_bytes = BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)
        
        filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return excel_bytes, filename
    
    @staticmethod
    def to_pdf(report_data: Dict[str, Any]) -> Tuple[BytesIO, str]:
        """
        Export report to PDF format.
        
        Requires: WeasyPrint or ReportLab package
        
        Args:
            report_data: Report data dictionary
            
        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        logger.info(f"Exporting report to PDF: {report_data.get('report_type')}")
        
        try:
            from weasyprint import HTML, CSS
            from io import BytesIO
        except ImportError:
            logger.error("WeasyPrint not installed. Install with: pip install weasyprint")
            raise ImportError("WeasyPrint is required for PDF export")
        
        # Generate HTML
        html_content = ReportExportService._generate_pdf_html(report_data)
        
        # Convert to PDF
        pdf_bytes = BytesIO()
        HTML(string=html_content).write_pdf(pdf_bytes)
        pdf_bytes.seek(0)
        
        report_type = report_data.get('report_type')
        filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return pdf_bytes, filename
    
    # CSV Export Helpers
    
    @staticmethod
    def _export_ledger_csv(writer, report_data: Dict) -> None:
        """Export General Ledger to CSV."""
        writer.writerow(['Date', 'Reference', 'Description', 'Debit', 'Credit', 'Balance'])
        
        for line in report_data.get('lines', []):
            writer.writerow([
                line['date'],
                line['reference'],
                line['description'],
                f"{line['debit']:.2f}",
                f"{line['credit']:.2f}",
                f"{line['balance']:.2f}",
            ])
        
        writer.writerow([])
        writer.writerow(['TOTALS', '', '', 
                        f"{report_data['totals']['debit']:.2f}",
                        f"{report_data['totals']['credit']:.2f}",
                        f"{report_data['totals']['ending_balance']:.2f}"])
    
    @staticmethod
    def _export_trial_balance_csv(writer, report_data: Dict) -> None:
        """Export Trial Balance to CSV."""
        writer.writerow(['Account Code', 'Account Name', 'Type', 'Debit', 'Credit'])
        
        for line in report_data.get('lines', []):
            writer.writerow([
                line['code'],
                line['name'],
                line['type'],
                f"{line['debit']:.2f}",
                f"{line['credit']:.2f}",
            ])
        
        writer.writerow([])
        writer.writerow(['TOTALS', '', '',
                        f"{report_data['totals']['debit']:.2f}",
                        f"{report_data['totals']['credit']:.2f}"])
        
        if report_data.get('is_balanced'):
            writer.writerow(['BALANCED: YES'])
        else:
            writer.writerow(['BALANCED: NO - OUT OF BALANCE'])
    
    @staticmethod
    def _export_pl_csv(writer, report_data: Dict) -> None:
        """Export P&L to CSV."""
        for line in report_data.get('lines', []):
            if line['type'] == 'header':
                writer.writerow([])
                writer.writerow([line['section'].upper()])
            elif line['type'] == 'detail':
                writer.writerow(['  ' + line.get('account_code', ''), f"{line['value']:.2f}"])
            elif line['type'] == 'subtotal':
                writer.writerow([line['label'], f"{line['value']:.2f}"])
            elif line['type'] == 'total':
                writer.writerow([])
                writer.writerow([line['label'], f"{line['value']:.2f}"])
    
    @staticmethod
    def _export_bs_csv(writer, report_data: Dict) -> None:
        """Export Balance Sheet to CSV."""
        for line in report_data.get('lines', []):
            if line['type'] == 'header':
                writer.writerow([])
                writer.writerow([line['section'].upper()])
            elif line['type'] == 'detail':
                writer.writerow(['  ' + line.get('account_code', ''), f"{line['value']:.2f}"])
            elif line['type'] == 'subtotal':
                writer.writerow([line['label'], f"{line['value']:.2f}"])
    
    @staticmethod
    def _export_cf_csv(writer, report_data: Dict) -> None:
        """Export Cash Flow to CSV."""
        for line in report_data.get('lines', []):
            if line['type'] == 'header':
                writer.writerow([])
                writer.writerow([line['section'].upper()])
            elif line['type'] == 'detail':
                writer.writerow(['  Activities', f"{line.get('value', 0):.2f}"])
            elif line['type'] == 'subtotal':
                writer.writerow([line['section'] + ' (Subtotal)', f"{line['value']:.2f}"])
            elif line['type'] == 'total':
                writer.writerow([])
                writer.writerow([line['label'], f"{line['value']:.2f}"])
    
    @staticmethod
    def _export_ar_aging_csv(writer, report_data: Dict) -> None:
        """Export A/R Aging to CSV."""
        writer.writerow(['Account', 'Description', 'Days Old', 'Bucket', 'Balance'])
        
        for line in report_data.get('lines', []):
            writer.writerow([
                line['account'],
                line['description'],
                line['days_old'],
                line['bucket'],
                f"{line['balance']:.2f}",
            ])
        
        writer.writerow([])
        writer.writerow(['AGING SUMMARY'])
        writer.writerow(['0-30 Days', f"{report_data['aging_summary']['0-30']:.2f}"])
        writer.writerow(['31-60 Days', f"{report_data['aging_summary']['31-60']:.2f}"])
        writer.writerow(['61-90 Days', f"{report_data['aging_summary']['61-90']:.2f}"])
        writer.writerow(['90+ Days', f"{report_data['aging_summary']['90+']:.2f}"])
        writer.writerow(['TOTAL', f"{report_data['total']:.2f}"])
    
    # Excel Export Helpers
    
    @staticmethod
    def _export_ledger_excel(ws, report_data: Dict, row: int, header_fill, header_font_white, border, total_fill, total_font) -> int:
        """Export General Ledger to Excel sheet."""
        # Headers
        headers = ['Date', 'Reference', 'Description', 'Debit', 'Credit', 'Balance']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row, col, header)
            cell.fill = header_fill
            cell.font = header_font_white
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
        row += 1
        
        # Data
        for line in report_data.get('lines', []):
            ws.cell(row, 1, line['date'])
            ws.cell(row, 2, line['reference'])
            ws.cell(row, 3, line['description'])
            ws.cell(row, 4, float(line['debit']))
            ws.cell(row, 5, float(line['credit']))
            ws.cell(row, 6, float(line['balance']))
            row += 1
        
        # Totals
        row += 1
        ws.cell(row, 1, 'TOTALS')
        ws.cell(row, 4, float(report_data['totals']['debit']))
        ws.cell(row, 5, float(report_data['totals']['credit']))
        ws.cell(row, 6, float(report_data['totals']['ending_balance']))
        
        for col in range(1, 7):
            ws.cell(row, col).fill = total_fill
            ws.cell(row, col).font = total_font
        
        return row + 1
    
    @staticmethod
    def _export_trial_balance_excel(ws, report_data: Dict, row: int, header_fill, header_font_white, border, total_fill, total_font) -> int:
        """Export Trial Balance to Excel sheet."""
        headers = ['Code', 'Name', 'Type', 'Debit', 'Credit']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row, col, header)
            cell.fill = header_fill
            cell.font = header_font_white
            cell.border = border
        row += 1
        
        for line in report_data.get('lines', []):
            ws.cell(row, 1, line['code'])
            ws.cell(row, 2, line['name'])
            ws.cell(row, 3, line['type'])
            ws.cell(row, 4, float(line['debit']))
            ws.cell(row, 5, float(line['credit']))
            row += 1
        
        row += 1
        ws.cell(row, 1, 'TOTALS')
        ws.cell(row, 4, float(report_data['totals']['debit']))
        ws.cell(row, 5, float(report_data['totals']['credit']))
        
        for col in range(1, 6):
            ws.cell(row, col).fill = total_fill
            ws.cell(row, col).font = total_font
        
        return row + 1
    
    @staticmethod
    def _export_pl_excel(ws, report_data: Dict, row: int, header_fill, header_font_white, border, total_fill, total_font) -> int:
        """Export P&L to Excel sheet."""
        from openpyxl.styles import Alignment
        
        for line in report_data.get('lines', []):
            if line['type'] == 'header':
                row += 1
                ws.cell(row, 1, line['section'].upper())
                ws.cell(row, 1).font = Font(bold=True, size=11)
            elif line['type'] == 'detail':
                ws.cell(row, 1, '  ' + line.get('account_code', ''))
                ws.cell(row, 2, float(line['value']))
            elif line['type'] == 'subtotal':
                ws.cell(row, 1, line['label'])
                ws.cell(row, 2, float(line['value']))
                ws.cell(row, 1).fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
                ws.cell(row, 1).font = Font(bold=True)
            elif line['type'] == 'total':
                row += 1
                ws.cell(row, 1, line['label'])
                ws.cell(row, 2, float(line['value']))
                for col in range(1, 3):
                    ws.cell(row, col).fill = total_fill
                    ws.cell(row, col).font = total_font
            row += 1
        
        return row
    
    @staticmethod
    def _export_bs_excel(ws, report_data: Dict, row: int, header_fill, header_font_white, border, total_fill, total_font) -> int:
        """Export Balance Sheet to Excel sheet."""
        from openpyxl.styles import Font, PatternFill
        
        for line in report_data.get('lines', []):
            if line['type'] == 'header':
                row += 1
                ws.cell(row, 1, line['section'].upper())
                ws.cell(row, 1).font = Font(bold=True, size=11)
            elif line['type'] == 'detail':
                ws.cell(row, 1, '  ' + line.get('account_code', ''))
                ws.cell(row, 2, float(line['value']))
            elif line['type'] == 'subtotal':
                ws.cell(row, 1, line['label'])
                ws.cell(row, 2, float(line['value']))
                ws.cell(row, 1).fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
                ws.cell(row, 1).font = Font(bold=True)
            row += 1
        
        return row
    
    @staticmethod
    def _export_cf_excel(ws, report_data: Dict, row: int, header_fill, header_font_white, border, total_fill, total_font) -> int:
        """Export Cash Flow to Excel sheet."""
        from openpyxl.styles import Font, PatternFill
        
        for line in report_data.get('lines', []):
            if line['type'] == 'header':
                row += 1
                ws.cell(row, 1, line['section'].upper())
                ws.cell(row, 1).font = Font(bold=True, size=11)
            elif line['type'] == 'detail':
                ws.cell(row, 1, '  Activities')
                ws.cell(row, 2, float(line.get('value', 0)))
            elif line['type'] == 'subtotal':
                ws.cell(row, 1, line['section'] + ' (Subtotal)')
                ws.cell(row, 2, float(line['value']))
                ws.cell(row, 1).fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
                ws.cell(row, 1).font = Font(bold=True)
            elif line['type'] == 'total':
                row += 1
                ws.cell(row, 1, line['label'])
                ws.cell(row, 2, float(line['value']))
                for col in range(1, 3):
                    ws.cell(row, col).fill = total_fill
                    ws.cell(row, col).font = total_font
            row += 1
        
        return row
    
    @staticmethod
    def _export_ar_aging_excel(ws, report_data: Dict, row: int, header_fill, header_font_white, border, total_fill, total_font) -> int:
        """Export A/R Aging to Excel sheet."""
        headers = ['Account', 'Description', 'Days Old', 'Bucket', 'Balance']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row, col, header)
            cell.fill = header_fill
            cell.font = header_font_white
            cell.border = border
        row += 1
        
        for line in report_data.get('lines', []):
            ws.cell(row, 1, line['account'])
            ws.cell(row, 2, line['description'])
            ws.cell(row, 3, line['days_old'])
            ws.cell(row, 4, line['bucket'])
            ws.cell(row, 5, float(line['balance']))
            row += 1
        
        row += 2
        ws.cell(row, 1, 'AGING SUMMARY')
        ws.cell(row, 1).font = Font(bold=True, size=11)
        row += 1
        
        for label, amount in [('0-30 Days', '0-30'), ('31-60 Days', '31-60'), ('61-90 Days', '61-90'), ('90+ Days', '90+')]:
            ws.cell(row, 1, label)
            ws.cell(row, 2, float(report_data['aging_summary'][amount]))
            row += 1
        
        ws.cell(row, 1, 'TOTAL')
        ws.cell(row, 2, float(report_data['total']))
        for col in range(1, 3):
            ws.cell(row, col).fill = total_fill
            ws.cell(row, col).font = Font(bold=True)
        
        return row + 1
    
    # PDF Generation Helper
    
    @staticmethod
    def _generate_pdf_html(report_data: Dict) -> str:
        """Generate HTML for PDF rendering."""
        report_type = report_data.get('report_type')
        title = f"{report_type.replace('_', ' ').title()} Report"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; }}
                .title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .meta {{ font-size: 12px; color: #666; margin-bottom: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th {{ background-color: #4472C4; color: white; padding: 8px; text-align: left; border: 1px solid #999; }}
                td {{ padding: 8px; border: 1px solid #999; }}
                .total {{ background-color: #E7E6E6; font-weight: bold; }}
                .number {{ text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="title">{title}</div>
                <div class="meta">Organization: {report_data.get('organization')}</div>
        """
        
        if 'as_of_date' in report_data:
            html += f"<div class='meta'>As of: {report_data['as_of_date']}</div>"
        elif 'period' in report_data:
            html += f"<div class='meta'>Period: {report_data['period']}</div>"
        
        html += f"<div class='meta'>Generated: {report_data['generated_at']}</div></div>"
        
        # Add table based on type
        if report_type == 'general_ledger':
            html += ReportExportService._generate_ledger_html_table(report_data)
        elif report_type == 'trial_balance':
            html += ReportExportService._generate_trial_balance_html_table(report_data)
        elif report_type == 'profit_loss':
            html += ReportExportService._generate_pl_html_table(report_data)
        elif report_type == 'balance_sheet':
            html += ReportExportService._generate_bs_html_table(report_data)
        elif report_type == 'cash_flow':
            html += ReportExportService._generate_cf_html_table(report_data)
        elif report_type == 'ar_aging':
            html += ReportExportService._generate_ar_aging_html_table(report_data)
        
        html += "</body></html>"
        return html
    
    @staticmethod
    def _generate_ledger_html_table(report_data: Dict) -> str:
        """Generate HTML table for General Ledger."""
        html = """<table>
            <tr>
                <th>Date</th>
                <th>Reference</th>
                <th>Description</th>
                <th class="number">Debit</th>
                <th class="number">Credit</th>
                <th class="number">Balance</th>
            </tr>"""
        
        for line in report_data.get('lines', []):
            html += f"""<tr>
                <td>{line['date']}</td>
                <td>{line['reference']}</td>
                <td>{line['description']}</td>
                <td class="number">{line['debit']:.2f}</td>
                <td class="number">{line['credit']:.2f}</td>
                <td class="number">{line['balance']:.2f}</td>
            </tr>"""
        
        html += f"""<tr class="total">
            <td colspan="3">TOTALS</td>
            <td class="number">{report_data['totals']['debit']:.2f}</td>
            <td class="number">{report_data['totals']['credit']:.2f}</td>
            <td class="number">{report_data['totals']['ending_balance']:.2f}</td>
        </tr></table>"""
        
        return html
    
    @staticmethod
    def _generate_trial_balance_html_table(report_data: Dict) -> str:
        """Generate HTML table for Trial Balance."""
        html = """<table>
            <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Type</th>
                <th class="number">Debit</th>
                <th class="number">Credit</th>
            </tr>"""
        
        for line in report_data.get('lines', []):
            html += f"""<tr>
                <td>{line['code']}</td>
                <td>{line['name']}</td>
                <td>{line['type']}</td>
                <td class="number">{line['debit']:.2f}</td>
                <td class="number">{line['credit']:.2f}</td>
            </tr>"""
        
        html += f"""<tr class="total">
            <td colspan="3">TOTALS</td>
            <td class="number">{report_data['totals']['debit']:.2f}</td>
            <td class="number">{report_data['totals']['credit']:.2f}</td>
        </tr></table>"""
        
        balanced_status = "YES" if report_data.get('is_balanced') else "NO - OUT OF BALANCE"
        html += f"<p><strong>Balanced: {balanced_status}</strong></p>"
        
        return html
    
    @staticmethod
    def _generate_pl_html_table(report_data: Dict) -> str:
        """Generate HTML table for P&L Statement."""
        html = "<table>"
        
        current_section = None
        for line in report_data.get('lines', []):
            if line.get('section') != current_section:
                if current_section is not None:
                    html += "</table><table>"
                current_section = line.get('section')
                html += f"<tr><th colspan='2'>{current_section.upper()}</th></tr>"
            
            if line['type'] == 'detail':
                html += f"""<tr>
                    <td>{line.get('account_code', '')}</td>
                    <td class="number">{line['value']:.2f}</td>
                </tr>"""
            elif line['type'] == 'subtotal':
                html += f"""<tr class="total">
                    <td>{line['label']}</td>
                    <td class="number">{line['value']:.2f}</td>
                </tr>"""
            elif line['type'] == 'total':
                html += f"""<tr class="total">
                    <td><strong>{line['label']}</strong></td>
                    <td class="number"><strong>{line['value']:.2f}</strong></td>
                </tr>"""
        
        html += "</table>"
        return html
    
    @staticmethod
    def _generate_bs_html_table(report_data: Dict) -> str:
        """Generate HTML table for Balance Sheet."""
        # Similar to P&L
        return ReportExportService._generate_pl_html_table(report_data)
    
    @staticmethod
    def _generate_cf_html_table(report_data: Dict) -> str:
        """Generate HTML table for Cash Flow."""
        return ReportExportService._generate_pl_html_table(report_data)
    
    @staticmethod
    def _generate_ar_aging_html_table(report_data: Dict) -> str:
        """Generate HTML table for A/R Aging."""
        html = """<table>
            <tr>
                <th>Account</th>
                <th>Description</th>
                <th>Days Old</th>
                <th>Bucket</th>
                <th class="number">Balance</th>
            </tr>"""
        
        for line in report_data.get('lines', []):
            html += f"""<tr>
                <td>{line['account']}</td>
                <td>{line['description']}</td>
                <td>{line['days_old']}</td>
                <td>{line['bucket']}</td>
                <td class="number">{line['balance']:.2f}</td>
            </tr>"""
        
        html += """</table>
            <h3>Aging Summary</h3>
            <table>
                <tr><th>Period</th><th class="number">Amount</th></tr>"""
        
        for period, label in [('0-30', '0-30 Days'), ('31-60', '31-60 Days'), ('61-90', '61-90 Days'), ('90+', '90+ Days')]:
            html += f"""<tr>
                <td>{label}</td>
                <td class="number">{report_data['aging_summary'][period]:.2f}</td>
            </tr>"""
        
        html += f"""<tr class="total">
                <td><strong>TOTAL</strong></td>
                <td class="number"><strong>{report_data['total']:.2f}</strong></td>
            </tr></table>"""
        
        return html
