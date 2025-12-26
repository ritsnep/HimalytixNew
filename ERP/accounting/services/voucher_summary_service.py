from decimal import Decimal

class VoucherSummaryService:
    @staticmethod
    def compute_from_lines(lines, charges=None):
        total_debit = sum(Decimal(str(l.get('debit_amount') or '0')) for l in lines if not l.get('DELETE'))
        total_credit = sum(Decimal(str(l.get('credit_amount') or '0')) for l in lines if not l.get('DELETE'))
        total_quantity = sum(Decimal(str(l.get('quantity') or '0')) for l in lines if not l.get('DELETE'))
        count = sum(1 for l in lines if not l.get('DELETE'))
        total_charges = sum(Decimal(str(c.get('amount') or '0')) for c in (charges or []) if not c.get('DELETE'))
        balance_diff = total_debit - total_credit
        return {
            'total_lines': count,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'balance_diff': balance_diff,
            'total_quantity': total_quantity,
            'total_charges': total_charges,
        }