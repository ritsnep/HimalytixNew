from decimal import Decimal

from django.test import SimpleTestCase

from purchasing.services.matching_service import validate_3way_match, calculate_variance


class MatchingServiceTests(SimpleTestCase):
    def test_calculate_variance(self):
        variances = calculate_variance(
            po_qty=Decimal("10"),
            gr_qty=Decimal("9"),
            inv_qty=Decimal("9"),
            po_unit_price=Decimal("5"),
            inv_unit_price=Decimal("5.50"),
        )
        self.assertEqual(variances["qty_variance_po_vs_gr"], Decimal("-1"))
        self.assertEqual(variances["qty_variance_gr_vs_inv"], Decimal("0"))
        self.assertEqual(variances["price_variance"], Decimal("0.50"))

    def test_perfect_match_passes(self):
        po_lines = [{"id": 1, "quantity_ordered": Decimal("5"), "unit_price": Decimal("10")}]
        gr_lines = [{"po_line_id": 1, "quantity_received": Decimal("5")}]
        inv_lines = [{"po_line_id": 1, "quantity_invoiced": Decimal("5"), "unit_price": Decimal("10")}]

        result = validate_3way_match(po_lines, gr_lines, inv_lines)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["lines"][0]["status"], "pass")

    def test_over_receipt_fails(self):
        po_lines = [{"id": 1, "quantity_ordered": Decimal("5"), "unit_price": Decimal("10")}]
        gr_lines = [{"po_line_id": 1, "quantity_received": Decimal("6")}]
        inv_lines = [{"po_line_id": 1, "quantity_invoiced": Decimal("5"), "unit_price": Decimal("10")}]

        result = validate_3way_match(po_lines, gr_lines, inv_lines, qty_tolerance=Decimal("0"))
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["lines"][0]["over_received"])

    def test_over_invoice_fails(self):
        po_lines = [{"id": 1, "quantity_ordered": Decimal("5"), "unit_price": Decimal("10")}]
        gr_lines = [{"po_line_id": 1, "quantity_received": Decimal("5")}]
        inv_lines = [{"po_line_id": 1, "quantity_invoiced": Decimal("6"), "unit_price": Decimal("10")}]

        result = validate_3way_match(po_lines, gr_lines, inv_lines, qty_tolerance=Decimal("0"))
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["lines"][0]["over_invoiced"])

    def test_price_variance_respects_tolerance(self):
        po_lines = [{"id": 1, "quantity_ordered": Decimal("5"), "unit_price": Decimal("10")}]
        gr_lines = [{"po_line_id": 1, "quantity_received": Decimal("5")}]
        inv_lines = [{"po_line_id": 1, "quantity_invoiced": Decimal("5"), "unit_price": Decimal("10.05")}]

        result_fail = validate_3way_match(po_lines, gr_lines, inv_lines, price_tolerance=Decimal("0.01"))
        self.assertEqual(result_fail["status"], "fail")

        result_pass = validate_3way_match(po_lines, gr_lines, inv_lines, price_tolerance=Decimal("0.10"))
        self.assertEqual(result_pass["status"], "warn")
