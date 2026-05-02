from pathlib import Path
import unittest

from labview.parser import LabReport

FIXTURE = Path("tests/fixtures/lab_report.html")


class ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = LabReport.from_file(FIXTURE)

    def test_parses_summary_table_from_fixture(self) -> None:
        summary = self.report.require_table("summary")

        self.assertEqual(summary.rows[0][0], "Summary")
        self.assertEqual(summary.rows[1][0], "coverage - Sum")
        self.assertEqual(summary.rows[1][1], "1")

    def test_expands_rowspans_in_error_table(self) -> None:
        errors = self.report.require_table("unexplained-errors")

        self.assertEqual(
            errors.rows[0][:4],
            (
                "Unexplained errors",
                "algorithm",
                "domain",
                "problem",
            ),
        )
        self.assertEqual(errors.rows[2][0], errors.rows[1][0])
        self.assertEqual(errors.rows[2][1], "algo-b")


if __name__ == "__main__":
    unittest.main()
