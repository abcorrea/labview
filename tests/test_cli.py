from pathlib import Path
import unittest

from labview.cli import _format_attributes, _select_tables, _split_values
from labview.parser import LabReport

FIXTURE = Path("tests/fixtures/lab_report.html")


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = LabReport.from_file(FIXTURE)

    def test_default_selection_is_summary(self) -> None:
        tables = _select_tables(self.report, attributes=[], domains=[], include_errors=False)

        self.assertEqual([table.section_id for table in tables], ["summary"])

    def test_attribute_and_domain_selection(self) -> None:
        tables = _select_tables(
            self.report,
            attributes=["coverage", "search_time"],
            domains=["blocksworld"],
            include_errors=True,
        )

        self.assertEqual(
            [table.section_id for table in tables],
            [
                "unexplained-errors",
                "coverage",
                "coverage-blocksworld",
                "search_time",
                "search_time-blocksworld",
            ],
        )

    def test_summary_option_keeps_summary_first(self) -> None:
        tables = _select_tables(
            self.report,
            attributes=["coverage"],
            domains=[],
            include_errors=True,
            include_summary=True,
        )

        self.assertEqual(
            [table.section_id for table in tables],
            ["summary", "unexplained-errors", "coverage"],
        )

    def test_summary_option_does_not_duplicate_default_summary(self) -> None:
        tables = _select_tables(
            self.report,
            attributes=[],
            domains=[],
            include_errors=False,
            include_summary=True,
        )

        self.assertEqual([table.section_id for table in tables], ["summary"])

    def test_split_values_accepts_spaces_and_commas(self) -> None:
        self.assertEqual(
            _split_values(["coverage,search_time", "total_time"]),
            ["coverage", "search_time", "total_time"],
        )

    def test_format_attributes_lists_available_attribute_tables(self) -> None:
        self.assertEqual(_format_attributes(self.report), "coverage\nsearch_time")


if __name__ == "__main__":
    unittest.main()
