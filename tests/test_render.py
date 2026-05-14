import unittest

from labview.parser import Table
from labview.render import render_table


class RenderTests(unittest.TestCase):
    def test_table_title_is_markdown_heading(self) -> None:
        table = Table(
            "score",
            (
                ("score", "algo-a"),
                ("task-1", "1"),
            ),
        )

        rendered = render_table(table, width=120)

        self.assertTrue(rendered.startswith("# score\n"))

    def test_highlight_marks_row_maxima(self) -> None:
        table = Table(
            "score",
            (
                ("score", "algo-a", "algo-b", "algo-c"),
                ("task-1", "1", "3", "2"),
                ("task-2", "5", "5", "4"),
            ),
        )

        rendered = render_table(table, width=120, color=True, highlight="max")

        self.assertIn("\033[1m\033[4m3", rendered)
        self.assertEqual(rendered.count("\033[1m\033[4m5"), 2)

    def test_highlight_marks_row_minima(self) -> None:
        table = Table(
            "score",
            (
                ("score", "algo-a", "algo-b", "algo-c"),
                ("task-1", "1", "3", "2"),
            ),
        )

        rendered = render_table(table, width=120, color=True, highlight="min")

        self.assertIn("\033[1m\033[4m1", rendered)

    def test_plain_output_has_no_ansi_codes(self) -> None:
        table = Table(
            "score",
            (
                ("score", "algo-a", "algo-b"),
                ("task-1", "1", "3"),
            ),
        )

        rendered = render_table(table, width=120, color=False, highlight="max")

        self.assertNotIn("\033[", rendered)

    def test_compacted_algorithm_legend_uses_column_colors(self) -> None:
        table = Table(
            "score",
            (
                ("score", "very-long-algorithm-a", "very-long-algorithm-b", "very-long-algorithm-c"),
                ("task-1", "1", "3", "2"),
            ),
        )

        rendered = render_table(table, width=40, color=True)

        self.assertIn("\033[36mA1", rendered)
        self.assertIn("\033[35mA2", rendered)

    def test_algorithm_colors_only_apply_to_headers_and_legend(self) -> None:
        table = Table(
            "score",
            (
                ("score", "algo-a", "algo-b"),
                ("task-1", "1", "3"),
            ),
        )

        rendered = render_table(table, width=120, color=True)

        self.assertIn("\033[1m\033[36malgo-a", rendered)
        self.assertNotIn("\033[36m1", rendered)


if __name__ == "__main__":
    unittest.main()
