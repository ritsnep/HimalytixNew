from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from accounting.views.journal_entry import _build_lines


class BuildLinesNumberingTest(SimpleTestCase):
    @patch("accounting.views.journal_entry._resolve_account")
    def test_blank_rows_do_not_create_numbering_gaps(self, mock_resolve_account):
        mock_resolve_account.return_value = object()

        rows = [
            {
                "account": "1000 - Cash",
                "dr": "50",
                "cr": "0",
            },
            {
                "account": "",
                "dr": "",
                "cr": "",
            },
            {
                "account": "1000 - Cash",
                "dr": "0",
                "cr": "50",
            },
        ]

        lines = _build_lines(rows, Mock(), udf_line_defs=[])

        self.assertEqual(len(lines), 2)
        self.assertEqual([line["line_number"] for line in lines], [1, 2])
        self.assertEqual(mock_resolve_account.call_count, 2)
