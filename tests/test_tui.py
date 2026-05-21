import unittest
from pathlib import Path
import curses
import argparse

from labview.parser import LabReport
from labview.tui import (
    parse_ansi_to_curses_segments,
    parse_tui_command,
    escape_latex,
    export_to_latex,
    get_report_domains,
    get_report_configurations,
    get_command_input,
    _generate_list_text,
)

FIXTURE = Path("tests/fixtures/lab_report.html")


class TuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = LabReport.from_file(FIXTURE)

    def test_parse_ansi_to_curses_segments_plain(self) -> None:
        segments = parse_ansi_to_curses_segments("hello world")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "hello world")
        self.assertEqual(segments[0][1], curses.A_NORMAL)

    def test_parse_ansi_to_curses_segments_formatting(self) -> None:
        # Bold text
        segments = parse_ansi_to_curses_segments("\033[1mhello\033[0m world")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][0], "hello")
        self.assertEqual(segments[0][1], curses.A_BOLD)
        self.assertEqual(segments[1][0], " world")
        self.assertEqual(segments[1][1], curses.A_NORMAL)

        # Underline text
        segments = parse_ansi_to_curses_segments("\033[4mhello\033[0m")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "hello")
        self.assertEqual(segments[0][1], curses.A_UNDERLINE)

    def test_parse_tui_command_quit(self) -> None:
        state = {"quit": False, "view_mode": "table"}
        success, err = parse_tui_command("q", state, self.report)
        self.assertFalse(success)
        self.assertIsNotNone(err)
        self.assertFalse(state["quit"])

        state = {"quit": False, "view_mode": "table"}
        success, err = parse_tui_command("quit", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertTrue(state["quit"])

    def test_parse_tui_command_help(self) -> None:
        state = {"quit": False, "view_mode": "table"}
        success, err = parse_tui_command("help", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["view_mode"], "help")

        state = {"quit": False, "view_mode": "table"}
        success, err = parse_tui_command("?", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["view_mode"], "help")

    def test_parse_tui_command_list(self) -> None:
        state = {"quit": False, "view_mode": "table"}
        success, err = parse_tui_command("list", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["view_mode"], "list")

    def test_generate_list_text(self) -> None:
        text = _generate_list_text(self.report)
        self.assertIn("Attributes:", text)
        self.assertIn("coverage", text)
        self.assertIn("Configurations:", text)
        self.assertIn("1: algo-a", text)
        self.assertIn("2: algo-b", text)
        self.assertIn("Domains:", text)
        self.assertIn("blocksworld", text)

    def test_parse_tui_command_attributes(self) -> None:
        state = {
            "attributes": [],
            "view_mode": "table",
            "quit": False,
        }
        success, err = parse_tui_command("attribute coverage", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["attributes"], ["coverage"])

        # Multiple attributes with plural alias
        success, err = parse_tui_command("attributes coverage expansions", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["attributes"], ["coverage", "expansions"])

        # Clearing attributes
        success, err = parse_tui_command("attribute clear", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["attributes"], [])

    def test_parse_tui_command_configurations(self) -> None:
        state = {
            "configurations": [],
            "view_mode": "table",
            "quit": False,
        }
        success, err = parse_tui_command("configuration algo-a 2", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        # '2' is resolved to 'algo-b' because 'algo-b' is the 2nd config in get_report_configurations
        self.assertEqual(state["configurations"], ["algo-a", "algo-b"])

        # Multiple configurations with plural alias
        success, err = parse_tui_command("configurations algo-a algo-b", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["configurations"], ["algo-a", "algo-b"])

        # Clear configurations
        success, err = parse_tui_command("configuration none", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["configurations"], [])

    def test_parse_tui_command_highlight(self) -> None:
        state = {
            "highlight": None,
            "view_mode": "table",
            "quit": False,
        }
        success, err = parse_tui_command("highlight max", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(state["highlight"], "max")

        # Clear highlight
        success, err = parse_tui_command("highlight off", state, self.report)
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertIsNone(state["highlight"])

    def test_parse_tui_command_invalid(self) -> None:
        state = {
            "attributes": [],
            "view_mode": "table",
            "quit": False,
        }
        success, err = parse_tui_command("invalid_cmd foo", state, self.report)
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_get_report_domains(self) -> None:
        domains = get_report_domains(self.report)
        self.assertEqual(domains, ["blocksworld"])

    def test_escape_latex(self) -> None:
        raw_text = "hello \\ { } % & _ # $ ^ ~ < > | world\nnew line"
        escaped = escape_latex(raw_text)
        expected = "hello \\textbackslash{} \\{ \\} \\% \\& \\_ \\# \\$ \\^{} \\~{} \\textless{} \\textgreater{} \\textbar{} world new line"
        self.assertEqual(escaped, expected)

    def test_export_to_latex(self) -> None:
        from labview.cli import _select_tables
        tables = _select_tables(
            self.report,
            attributes=["coverage"],
            domains=[],
            include_errors=False,
            include_summary=False,
        )
        latex_str = export_to_latex(tables, highlight=None)
        self.assertIn("\\toprule", latex_str)
        self.assertIn("\\midrule", latex_str)
        self.assertIn("\\bottomrule", latex_str)
        self.assertIn("\\begin{tabular}{lrr}", latex_str)
        self.assertIn("\\caption{coverage}", latex_str)
        self.assertNotIn("|", latex_str)

    def test_export_to_latex_highlight(self) -> None:
        from labview.cli import _select_tables
        tables = _select_tables(
            self.report,
            attributes=["coverage"],
            domains=["blocksworld"],
            include_errors=False,
            include_summary=False,
        )
        latex_str = export_to_latex(tables, highlight="max")
        self.assertIn("\\textbf{1}", latex_str)

    def test_parse_tui_command_tex(self) -> None:
        import os
        test_filename = "test_export.tex"
        if os.path.exists(test_filename):
            os.remove(test_filename)

        state = {
            "attributes": ["coverage"],
            "domains": [],
            "configurations": [],
            "errors": False,
            "summary": False,
            "highlight": None,
            "view_mode": "table",
            "quit": False,
        }

        try:
            success, err = parse_tui_command(f"tex {test_filename}", state, self.report)
            self.assertTrue(success)
            self.assertIsNone(err)
            self.assertEqual(state["success_message"], f"Exported 1 tables to {test_filename}")
            self.assertTrue(os.path.exists(test_filename))
            with open(test_filename, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("\\begin{table}", content)
            self.assertIn("coverage", content)
        finally:
            if os.path.exists(test_filename):
                os.remove(test_filename)

    def test_parse_tui_command_tex_usage_error(self) -> None:
        state = {
            "attributes": ["coverage"],
            "domains": [],
            "configurations": [],
            "errors": False,
            "summary": False,
            "highlight": None,
            "view_mode": "table",
            "quit": False,
        }
        success, err = parse_tui_command("tex", state, self.report)
        self.assertFalse(success)
        self.assertEqual(err, "Usage: /tex <filename>")

    def test_get_report_configurations(self) -> None:
        configs = get_report_configurations(self.report)
        self.assertEqual(configs, ["algo-a", "algo-b"])


class MockWindow:
    def __init__(self, key_sequence):
        self.key_sequence = []
        for item in key_sequence:
            if isinstance(item, str):
                self.key_sequence.extend(list(item))
            else:
                self.key_sequence.append(item)
        self.index = 0
        self.moves = []
        self.adds = []
        self.clears = 0

    def keypad(self, flag):
        pass

    def clear(self):
        self.clears += 1

    def getmaxyx(self):
        return (24, 80)

    def move(self, y, x):
        self.moves.append((y, x))

    def clrtoeol(self):
        self.clears += 1

    def addstr(self, y, x, text, attr=0):
        self.adds.append((y, x, text, attr))

    def refresh(self):
        pass

    def getch(self):
        if self.index < len(self.key_sequence):
            val = self.key_sequence[self.index]
            self.index += 1
            if isinstance(val, str):
                return ord(val)
            return val
        return 27  # Escape to exit if keys run out


class TuiAutocompleteTests(unittest.TestCase):
    def test_autocomplete_commands(self) -> None:
        # First TAB completed to 'highlight'
        win = MockWindow(["h", 9, 10])
        res = get_command_input(win, 0, 80, [], [], [])
        self.assertEqual(res, "highlight")

        # Second TAB completed to 'help'
        win = MockWindow(["h", 9, 9, 10])
        res = get_command_input(win, 0, 80, [], [], [])
        self.assertEqual(res, "help")

    def test_autocomplete_domains(self) -> None:
        domains = ["blocksworld", "gripper"]
        win = MockWindow(["d", "o", "m", 9, " ", "b", 9, 10])
        res = get_command_input(win, 0, 80, domains, [], [])
        self.assertEqual(res, "domain blocksworld")

        win = MockWindow(["d", "o", "m", 9, " ", 9, 10])  # Empty fragment completes to first
        res = get_command_input(win, 0, 80, domains, [], [])
        self.assertEqual(res, "domain blocksworld")

        win = MockWindow(["d", "o", "m", 9, " ", 9, 9, 10])  # Cycle to second
        res = get_command_input(win, 0, 80, domains, [], [])
        self.assertEqual(res, "domain gripper")

    def test_autocomplete_attributes(self) -> None:
        attrs = ["coverage", "search_time"]
        win = MockWindow(["a", "t", "t", 9, " ", "c", 9, 10])
        res = get_command_input(win, 0, 80, [], attrs, [])
        self.assertEqual(res, "attribute coverage")

        # Autocomplete second attribute after comma
        win = MockWindow(["a", "t", "t", 9, " ", "coverage", ",", "s", 9, 10])
        res = get_command_input(win, 0, 80, [], attrs, [])
        self.assertEqual(res, "attribute coverage,search_time")

    def test_autocomplete_configurations(self) -> None:
        configs = ["algo-a", "algo-b"]
        win = MockWindow(["c", "o", "n", 9, " ", "a", 9, 9, 10])
        res = get_command_input(win, 0, 80, [], [], configs)
        self.assertEqual(res, "configuration algo-b")

    def test_autocomplete_highlight(self) -> None:
        win = MockWindow(["h", "i", "g", "h", "l", "i", "g", "h", "t", " ", "m", 9, 9, 10])
        res = get_command_input(win, 0, 80, [], [], [])
        self.assertEqual(res, "highlight min")

    def test_tui_main_q_key_transition(self) -> None:
        import unittest.mock as mock
        mock_pad = mock.Mock()
        with mock.patch("curses.newpad", return_value=mock_pad):
            win = MockWindow(["/", "h", "e", "l", "p", 10, "q", "q"])
            with mock.patch("curses.curs_set"):
                with mock.patch("curses.has_colors", return_value=False):
                    args = argparse.Namespace(
                        attribute=None,
                        domain=None,
                        configuration=None,
                        errors=False,
                        summary=True,
                        highlight=None,
                        report="dummy.html",
                    )
                    from labview.tui import _tui_main
                    report = mock.Mock()
                    report.attribute_names.return_value = []
                    report.tables = {}
                    report.get_table.return_value = None
                    
                    result = _tui_main(win, report, args)
                    self.assertEqual(result, 0)

    def test_tui_main_q_key_transition_list(self) -> None:
        import unittest.mock as mock
        mock_pad = mock.Mock()
        with mock.patch("curses.newpad", return_value=mock_pad):
            win = MockWindow(["/", "l", "i", "s", "t", 10, "q", "q"])
            with mock.patch("curses.curs_set"):
                with mock.patch("curses.has_colors", return_value=False):
                    args = argparse.Namespace(
                        attribute=None,
                        domain=None,
                        configuration=None,
                        errors=False,
                        summary=True,
                        highlight=None,
                        report="dummy.html",
                    )
                    from labview.tui import _tui_main
                    report = mock.Mock()
                    report.attribute_names.return_value = []
                    report.tables = {}
                    report.get_table.return_value = None
                    
                    result = _tui_main(win, report, args)
                    self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
