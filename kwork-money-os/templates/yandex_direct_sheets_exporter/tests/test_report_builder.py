from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from report_builder import (  # noqa: E402
    CAMPAIGN_HEADERS,
    KEYWORD_HEADERS,
    build_campaign_rows,
    build_keyword_rows,
    build_report,
    mock_campaign_stats,
    mock_keyword_stats,
    safe_divide,
)


class ReportBuilderTests(unittest.TestCase):
    def test_safe_divide_handles_zero(self) -> None:
        self.assertEqual(safe_divide(10, 0), 0.0)
        self.assertEqual(safe_divide(1, 4), 0.25)

    def test_keyword_rows_have_expected_shape(self) -> None:
        rows = build_keyword_rows(mock_keyword_stats(), "2026-06-01", "2026-06-15")
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), len(KEYWORD_HEADERS))
        self.assertEqual(rows[0][0], "2026-06-01")
        self.assertGreater(rows[0][8], 0)

    def test_campaign_rows_have_weekday_and_metrics(self) -> None:
        rows = build_campaign_rows(mock_campaign_stats())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), len(CAMPAIGN_HEADERS))
        self.assertEqual(rows[0][1], "Понедельник")
        self.assertGreater(rows[0][10], 0)

    def test_build_report_returns_two_tables(self) -> None:
        tables = build_report(mock_keyword_stats(), mock_campaign_stats(), "2026-06-01", "2026-06-15")
        self.assertEqual([table.title for table in tables], ["Ключевые слова", "Кампании"])
        self.assertEqual(len(tables[0].rows), 2)
        self.assertEqual(len(tables[1].rows), 2)


if __name__ == "__main__":
    unittest.main()
