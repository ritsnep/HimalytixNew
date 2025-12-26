from decimal import Decimal, ROUND_HALF_UP


def _to_decimal(v):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


class PurchaseCalculator:
    """Simple, pure-Python purchase invoice calculator.

    Assumptions:
    - VAT default 13% (0.13) applied on net amount when `vat_applicable` is True.
      A per-line `vat_rate` (percent) overrides the default when provided.
    - Row discount may be `amount` or `percent`.
    - Header discount may be `amount` or `percent`; applied after row discounts.
    - Bill rounding is a numeric value added/subtracted to reach final total.
    - Amounts rounded to 2 decimal places using HALF_UP.
    """

    VAT_RATE = Decimal('0.13')

    def __init__(
        self,
        lines,
        header_discount_value=0,
        header_discount_type='amount',
        bill_rounding=0,
        default_vat_rate=None,
    ):
        self.lines = lines or []
        self.header_discount_value = _to_decimal(header_discount_value)
        self.header_discount_type = header_discount_type
        self.bill_rounding = _to_decimal(bill_rounding)
        self.default_vat_rate = (
            _to_decimal(default_vat_rate)
            if default_vat_rate is not None
            else self.VAT_RATE
        )

    def _round(self, val):
        val = _to_decimal(val)
        return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def compute(self):
        rows = []
        subtotal = Decimal('0')
        total_row_discounts = Decimal('0')
        total_net = Decimal('0')
        total_vat = Decimal('0')

        # First pass: compute gross, row discounts, net, vat per row
        for r in self.lines:
            qty = _to_decimal(r.get('qty') or 0)
            rate = _to_decimal(r.get('rate') or 0)
            gross = qty * rate

            # row discount
            rd_val = _to_decimal(r.get('row_discount_value') or 0)
            rd_type = r.get('row_discount_type') or 'amount'
            if rd_type == 'percent':
                row_discount = (gross * rd_val / Decimal('100'))
            else:
                row_discount = rd_val

            net = gross - row_discount
            vat_pct = r.get('vat_rate')
            vat_rate = self.default_vat_rate
            try:
                vat_rate_candidate = _to_decimal(vat_pct)
                if vat_rate_candidate and vat_rate_candidate > 0:
                    vat_rate = vat_rate_candidate / Decimal('100')
                elif vat_rate_candidate == 0:
                    vat_rate = Decimal('0')
            except Exception:
                vat_rate = self.default_vat_rate
            vat_app = bool(r.get('vat_applicable')) or vat_rate > 0
            vat_amount = net * vat_rate if vat_app else Decimal('0')
            amount = net + vat_amount

            subtotal += gross
            total_row_discounts += row_discount
            total_net += net
            total_vat += vat_amount

            rows.append({
                'qty': qty,
                'rate': rate,
                'gross': self._round(gross),
                'row_discount': self._round(row_discount),
                'net': self._round(net),
                'vat_amount': self._round(vat_amount),
                'amount': self._round(amount),
            })

        # Header discount applied on subtotal - total_row_discounts (i.e., on net after row discounts)
        base_for_header = subtotal - total_row_discounts
        if self.header_discount_type == 'percent' and base_for_header > 0:
            header_discount = (base_for_header * self.header_discount_value / Decimal('100'))
        else:
            header_discount = self.header_discount_value

        header_discount = self._round(header_discount)

        # Adjust totals: distribute header discount proportionally to net amounts for taxable calculation
        total_after_header = base_for_header - header_discount

        # recompute taxable amount (sum of nets where vat applied) proportionally
        vatable_net = Decimal('0')
        non_vatable_net = Decimal('0')
        # We did not keep vat_app flag per-row in rows; recompute from input
        for idx, r_in in enumerate(self.lines):
            vat_app = bool(r_in.get('vat_applicable'))
            net_before = rows[idx]['net']
            # proportionally reduce net by header discount share
            share = (net_before / total_net) if total_net > 0 else Decimal('0')
            net_after = net_before - (header_discount * share)
            if vat_app:
                vatable_net += net_after
            else:
                non_vatable_net += net_after
            rows[idx]['net_after_header'] = self._round(net_after)
            # recompute vat on net_after
            vat_amt = rows[idx]['net_after_header'] * self.VAT_RATE if vat_app else Decimal('0')
            rows[idx]['vat_amount'] = self._round(vat_amt)
            rows[idx]['amount'] = self._round(rows[idx]['net_after_header'] + rows[idx]['vat_amount'])

        # totals
        subtotal = self._round(subtotal)
        total_row_discounts = self._round(total_row_discounts)
        total_after_header = self._round(total_after_header)
        total_vat = sum(r['vat_amount'] for r in rows)
        total_vat = self._round(total_vat)

        taxable_amount = self._round(vatable_net)
        non_taxable_amount = self._round(non_vatable_net)

        grand_total = total_after_header + total_vat + self.bill_rounding
        grand_total = self._round(grand_total)

        totals = {
            'subtotal': subtotal,
            'total_row_discounts': total_row_discounts,
            'header_discount': header_discount,
            'total_after_header': total_after_header,
            'taxable_amount': taxable_amount,
            'non_taxable_amount': non_taxable_amount,
            'vat_amount': total_vat,
            'rounding': self._round(self.bill_rounding),
            'grand_total': grand_total,
        }

        return {'rows': rows, 'totals': totals}
