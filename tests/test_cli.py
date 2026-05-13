from pathlib import Path
import unittest

from labview.cli import _filter_configurations, _format_attributes, _select_tables, _split_values
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

    def test_filter_configurations_by_name(self) -> None:
        tables = _filter_configurations(
            [self.report.require_table("coverage")],
            ["algo-b"],
        )

        self.assertEqual(tables[0].rows[0], ("coverage", "algo-b"))
        self.assertEqual(tables[0].rows[1], ("blocksworld (2)", "2"))

    def test_filter_configurations_by_index(self) -> None:
        tables = _filter_configurations(
            [self.report.require_table("coverage")],
            ["1"],
        )

        self.assertEqual(tables[0].rows[0], ("coverage", "algo-a"))
        self.assertEqual(tables[0].rows[2], ("Sum (2)", "1"))

    def test_filter_configurations_accepts_multiple_values(self) -> None:
        tables = _filter_configurations(
            [self.report.require_table("coverage")],
            ["2", "algo-a"],
        )

        self.assertEqual(tables[0].rows[0], ("coverage", "algo-b", "algo-a"))

    def test_filter_configurations_filters_error_rows(self) -> None:
        tables = _filter_configurations(
            [self.report.require_table("unexplained-errors")],
            ["2"],
        )

        self.assertEqual(len(tables[0].rows), 2)
        self.assertEqual(tables[0].rows[1][1], "algo-b")

    def test_filter_configurations_rejects_unknown_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "no configuration 'missing'"):
            _filter_configurations([self.report.require_table("coverage")], ["missing"])

    def test_format_attributes_lists_available_attribute_tables(self) -> None:
        self.assertEqual(_format_attributes(self.report), "coverage\nsearch_time")


if __name__ == "__main__":
    unittest.main()
