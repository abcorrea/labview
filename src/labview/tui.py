from __future__ import annotations

import argparse
import curses
import re
import sys
from typing import TYPE_CHECKING

from .render import render_sections

from .parser import LabReport, Table


ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')


def run_tui(report: LabReport, args: argparse.Namespace) -> int:
    try:
        return curses.wrapper(_tui_main, report, args)
    except Exception as e:
        # Fallback to restore terminal cursor/settings if wrapper failed
        try:
            curses.echo()
            curses.nocbreak()
            curses.endwin()
        except Exception:
            pass
        raise e


def _tui_main(stdscr: curses.window, report: LabReport, args: argparse.Namespace) -> int:
    curses.curs_set(0)  # Hide cursor
    stdscr.keypad(True)

    if curses.has_colors():
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        # Define color pairs using default background (-1)
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_MAGENTA, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_GREEN, -1)
        curses.init_pair(5, curses.COLOR_BLUE, -1)
        curses.init_pair(6, curses.COLOR_RED, -1)
        # Status bar color pair (black text on cyan background)
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_CYAN)
        # Error message color pair (white text on red background)
        curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_RED)

    from .cli import _split_values
    state = {
        "attributes": _split_values(args.attribute),
        "domains": _split_values(args.domain),
        "configurations": _split_values(args.configuration),
        "errors": args.errors,
        "summary": args.summary,
        "highlight": args.highlight,
        "view_mode": "table",  # "table", "help", "list"
        "quit": False,
        "merges": [],
    }

    # Extract domains, attributes, and configurations lists for tab completion
    domains_list = get_report_domains(report)
    attributes_list = sorted(list(report.attribute_names()))
    configurations_list = get_report_configurations(report)

    scroll_y = 0
    scroll_x = 0

    last_rendered_text = ""
    pad: curses.window | None = None
    pad_lines = 0
    pad_cols = 0

    status_msg: str | None = None
    is_error = False

    while not state["quit"]:
        height, width = stdscr.getmaxyx()
        if height < 3 or width < 10:
            stdscr.clear()
            try:
                stdscr.addstr(0, 0, "Terminal too small!")
            except curses.error:
                pass
            stdscr.refresh()
            ch = stdscr.getch()
            if ch == ord("q"):
                break
            continue

        # Viewport layout
        viewport_height = height - 2
        viewport_width = width

        content_text = ""
        if state["view_mode"] == "help":
            content_text = _generate_help_text()
        elif state["view_mode"] == "list":
            content_text = _generate_list_text(report)
        else:
            from .cli import _filter_configurations, _select_tables
            try:
                tables = _select_tables(
                    report,
                    attributes=state["attributes"],
                    domains=state["domains"],
                    include_errors=state["errors"],
                    include_summary=state["summary"],
                )
                if state["configurations"]:
                    tables = _filter_configurations(tables, state["configurations"])
                if state.get("merges"):
                    tables = [_apply_merges_to_table(t, state["merges"]) for t in tables]
                content_text = render_sections(
                    tables,
                    color=True,
                    highlight=state["highlight"],
                    width=viewport_width,
                )
            except Exception as e:
                content_text = f"\033[1;31mError rendering table:\n{e}\033[0m"

        # Update curses pad if text or layout changed
        if content_text != last_rendered_text or pad is None:
            last_rendered_text = content_text
            # Force complete screen redraw to remove leftovers from previous layout
            stdscr.clear()
            lines = content_text.splitlines()
            pad_lines = len(lines)
            pad_cols = max(len(l) for l in lines) if lines else 0

            pad_lines = max(1, pad_lines)
            pad_cols = max(1, pad_cols)

            # Recreate pad with safety margins
            pad = curses.newpad(pad_lines + 5, pad_cols + 20)
            pad.erase()

            for y_idx, line in enumerate(lines):
                segments = parse_ansi_to_curses_segments(line)
                curr_x = 0
                for segment_text, attr in segments:
                    try:
                        pad.addstr(y_idx, curr_x, segment_text, attr)
                        curr_x += len(segment_text)
                    except curses.error:
                        pass

        # Draw status bar
        status_parts = [f"REPORT: {args.report}"]

        if state["attributes"]:
            status_parts.append(f"Attrs: {','.join(state['attributes'])}")
        else:
            status_parts.append("Attrs: [summary]")

        if state["domains"]:
            status_parts.append(f"Domains: {','.join(state['domains'])}")

        if state["configurations"]:
            status_parts.append(f"Configs: {','.join(state['configurations'])}")

        if state["highlight"]:
            status_parts.append(f"Highlight: {state['highlight']}")

        if state["errors"]:
            status_parts.append("[errors]")

        if state["summary"] and state["attributes"]:
            status_parts.append("[summary]")

        status_text = " | ".join(status_parts)
        status_line = f" {status_text}".ljust(width - 1)[:width - 1]

        stdscr.move(0, 0)
        status_attr = curses.color_pair(7) if curses.has_colors() else curses.A_REVERSE
        try:
            stdscr.addstr(0, 0, status_line, status_attr)
        except curses.error:
            pass

        # Draw prompt line at bottom
        if status_msg:
            prompt_line = f" {status_msg}"
            if is_error:
                prompt_attr = (
                    curses.color_pair(8) | curses.A_BOLD
                    if curses.has_colors()
                    else curses.A_REVERSE
                )
            else:
                prompt_attr = (
                    curses.color_pair(4) | curses.A_BOLD
                    if curses.has_colors()
                    else curses.A_REVERSE
                )
        else:
            prompt_line = " Press '/' to run a command, 'q' to quit, '?' / 'help' for help"
            prompt_attr = curses.A_DIM if hasattr(curses, "A_DIM") else curses.A_NORMAL

        prompt_line = prompt_line.ljust(width - 1)[:width - 1]
        stdscr.move(height - 1, 0)
        try:
            stdscr.addstr(height - 1, 0, prompt_line, prompt_attr)
        except curses.error:
            pass

        # Adjust and clamp scroll position
        max_scroll_y = max(0, pad_lines - viewport_height)
        max_scroll_x = max(0, pad_cols - viewport_width)
        scroll_y = min(scroll_y, max_scroll_y)
        scroll_x = min(scroll_x, max_scroll_x)

        # Clear viewport rows of stdscr to prevent leftover text from shorter layouts
        for y in range(1, height - 1):
            try:
                stdscr.move(y, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass

        stdscr.refresh()
        try:
            pad.refresh(scroll_y, scroll_x, 1, 0, height - 2, width - 1)
        except curses.error:
            pass

        ch = stdscr.getch()
        status_msg = None
        is_error = False

        # Return to table mode if pressing any navigation key from help/attributes views
        if state["view_mode"] != "table" and ch not in (
            ord("/"),
            ord("\\"),
            curses.KEY_RESIZE,
        ):
            state["view_mode"] = "table"
            last_rendered_text = ""
            continue

        # Handle viewport controls
        if ch in (curses.KEY_UP, ord("k")):
            scroll_y = max(0, scroll_y - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            scroll_y = min(max_scroll_y, scroll_y + 1)
        elif ch in (curses.KEY_LEFT, ord("h")):
            scroll_x = max(0, scroll_x - 4)
        elif ch in (curses.KEY_RIGHT, ord("l")):
            scroll_x = min(max_scroll_x, scroll_x + 4)
        elif ch in (curses.KEY_PPAGE, 2, ord("b")):  # Ctrl+B / PageUp
            scroll_y = max(0, scroll_y - viewport_height)
        elif ch in (curses.KEY_NPAGE, 6, ord("f")):  # Ctrl+F / PageDown
            scroll_y = min(max_scroll_y, scroll_y + viewport_height)
        elif ch in (curses.KEY_HOME, ord("g")):
            scroll_y = 0
        elif ch in (curses.KEY_END, ord("G")):
            scroll_y = max_scroll_y
        elif ch == ord("q"):
            break
        elif ch in (ord("/"), ord("\\")):
            cmd = get_command_input(
                stdscr,
                height - 1,
                width,
                domains=domains_list,
                attributes=attributes_list,
                configurations=configurations_list,
            )
            if cmd is not None:
                success, err = parse_tui_command(cmd, state, report)
                if not success:
                    status_msg = err
                    is_error = True
                elif "success_message" in state:
                    status_msg = state.pop("success_message")
                    is_error = False
        elif ch == curses.KEY_RESIZE:
            last_rendered_text = ""

    return 0


def get_command_input(
    stdscr: curses.window,
    prompt_row: int,
    max_cols: int,
    domains: list[str],
    attributes: list[str],
    configurations: list[str],
) -> str | None:
    try:
        curses.curs_set(1)  # Show cursor
    except curses.error:
        pass
    input_str: list[str] = []
    cursor_pos = 0
    cycle_state: dict = {}

    while True:
        stdscr.move(prompt_row, 0)
        stdscr.clrtoeol()
        # Prompt symbol
        try:
            stdscr.addstr(prompt_row, 0, "/")
            stdscr.addstr(prompt_row, 1, "".join(input_str))
            stdscr.move(prompt_row, 1 + cursor_pos)
        except curses.error:
            pass
        stdscr.refresh()

        ch = stdscr.getch()

        if ch in (10, 13):  # Enter
            break
        elif ch == 27:  # Esc
            input_str = []
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if cursor_pos > 0:
                input_str.pop(cursor_pos - 1)
                cursor_pos -= 1
            cycle_state = {}
        elif ch == curses.KEY_DC:  # Delete
            if cursor_pos < len(input_str):
                input_str.pop(cursor_pos)
            cycle_state = {}
        elif ch == curses.KEY_LEFT:
            cursor_pos = max(0, cursor_pos - 1)
            cycle_state = {}
        elif ch == curses.KEY_RIGHT:
            cursor_pos = min(len(input_str), cursor_pos + 1)
            cycle_state = {}
        elif ch == curses.KEY_HOME:
            cursor_pos = 0
            cycle_state = {}
        elif ch == curses.KEY_END:
            cursor_pos = len(input_str)
            cycle_state = {}
        elif ch == 9:  # TAB Key
            input_text = "".join(input_str)
            
            # Find matching prefix and fragment relative to last separator (space or comma)
            last_sep_idx = -1
            for i in range(len(input_text) - 1, -1, -1):
                if input_text[i] in (" ", ","):
                    last_sep_idx = i
                    break
            
            prefix = input_text[: last_sep_idx + 1]
            fragment = input_text[last_sep_idx + 1 :]
            
            if last_sep_idx == -1:
                # Autocomplete the command itself
                candidates = [
                    "attribute",
                    "domain",
                    "configuration",
                    "highlight",
                    "summary",
                    "errors",
                    "list",
                    "help",
                    "tex",
                    "quit",
                    "merge",
                ]
            else:
                # Autocomplete arguments based on the command context
                parts = input_text.strip().split()
                if not parts:
                    continue
                cmd_name = parts[0].lower()
                if cmd_name in ("domain", "domains", "--domain"):
                    candidates = domains
                elif cmd_name in ("attribute", "attributes", "--attribute"):
                    candidates = attributes
                elif cmd_name in ("configuration", "configurations", "--configuration"):
                    candidates = configurations
                elif cmd_name in ("highlight", "--highlight"):
                    candidates = ["max", "min", "off", "none", "clear"]
                elif cmd_name == "merge":
                    if len(parts) > 2 or (len(parts) == 2 and input_text.endswith(" ")):
                        candidates = domains
                    else:
                        continue
                else:
                    continue

            if cycle_state.get("active") and cycle_state.get("fragment") == fragment:
                matches = cycle_state["matches"]
                idx = (cycle_state["index"] + 1) % len(matches)
                cycle_state["index"] = idx
            else:
                matches = [
                    c
                    for c in candidates
                    if c.lower().startswith(fragment.lower())
                ]
                if not matches:
                    continue
                idx = 0
                cycle_state = {
                    "active": True,
                    "fragment": fragment,
                    "matches": matches,
                    "index": idx,
                }

            completed_val = matches[idx]
            new_input = prefix + completed_val
            input_str = list(new_input)
            cursor_pos = len(input_str)
            cycle_state["fragment"] = completed_val

        elif 32 <= ch < 127:  # Printable ascii characters
            input_str.insert(cursor_pos, chr(ch))
            cursor_pos += 1
            cycle_state = {}

    try:
        curses.curs_set(0)  # Hide cursor
    except curses.error:
        pass
    if not input_str and ch == 27:
        return None
    return "".join(input_str)


def parse_tui_command(cmd_str: str, state: dict, report: LabReport) -> tuple[bool, str | None]:
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return True, None

    parts = cmd_str.split()
    cmd_name = parts[0].lower()

    # Define explicitly allowed TUI commands (no single-letter options)
    allowed_commands = {
        "attribute", "attributes", "--attribute",
        "domain", "domains", "--domain",
        "configuration", "configurations", "--configuration",
        "errors", "--errors",
        "summary", "--summary",
        "highlight", "--highlight",
        "list", "list-attributes",
        "help", "?",
        "tex",
        "quit",
        "merge"
    }

    if cmd_name not in allowed_commands:
        return False, f"Unknown command: /{cmd_name}"

    # Normalize plural aliases to singular
    if cmd_name == "attributes":
        cmd_name = "attribute"
        parts[0] = "attribute"
    elif cmd_name == "domains":
        cmd_name = "domain"
        parts[0] = "domain"
    elif cmd_name == "configurations":
        cmd_name = "configuration"
        parts[0] = "configuration"

    # Map configuration index to name if applicable
    if cmd_name in ("configuration", "--configuration"):
        configs_list = get_report_configurations(report)
        new_parts = [parts[0]]
        for part in parts[1:]:
            subparts = part.split(",")
            mapped_subparts = []
            for sp in subparts:
                sp_strip = sp.strip()
                if sp_strip.isdigit():
                    idx = int(sp_strip)
                    if 1 <= idx <= len(configs_list):
                        mapped_subparts.append(configs_list[idx - 1])
                    else:
                        mapped_subparts.append(sp_strip)
                else:
                    mapped_subparts.append(sp)
            new_parts.append(",".join(mapped_subparts))
        parts = new_parts
        cmd_str = " ".join(parts)

    # Direct utility actions
    if cmd_name == "quit":
        state["quit"] = True
        return True, None
    elif cmd_name in ("help", "?"):
        state["view_mode"] = "help"
        return True, None
    elif cmd_name in ("list", "list-attributes"):
        state["view_mode"] = "list"
        return True, None
    elif cmd_name == "merge":
        if len(parts) == 2 and parts[1].lower() in ("none", "clear"):
            state["merges"] = []
            state["success_message"] = "Cleared all merges"
            state["view_mode"] = "table"
            return True, None
        if len(parts) < 3:
            return False, "Usage: /merge STRING domain1 domain2 ..."
        name = parts[1]
        domains = parts[2:]
        state["merges"] = [m for m in state["merges"] if m["name"].lower() != name.lower()]
        state["merges"].append({"name": name, "domains": domains})
        state["success_message"] = f"Merged domains into '{name}'"
        state["view_mode"] = "table"
        return True, None
    elif cmd_name == "tex":
        if len(parts) < 2:
            return False, "Usage: /tex <filename>"
        filename = cmd_str[len(parts[0]):].strip()
        filename = filename.strip('"\'')
        if not filename:
            return False, "Usage: /tex <filename>"
        try:
            from .cli import _filter_configurations, _select_tables
            tables = _select_tables(
                report,
                attributes=state["attributes"],
                domains=state["domains"],
                include_errors=state["errors"],
                include_summary=state["summary"],
            )
            if state["configurations"]:
                tables = _filter_configurations(tables, state["configurations"])
            if state.get("merges"):
                tables = [_apply_merges_to_table(t, state["merges"]) for t in tables]

            latex_content = export_to_latex(tables, highlight=state["highlight"])

            with open(filename, "w", encoding="utf-8") as f:
                f.write(latex_content)

            state["success_message"] = f"Exported {len(tables)} tables to {filename}"
            return True, None
        except Exception as e:
            return False, f"Failed to export to LaTeX: {e}"

    # Handle clearing filters (e.g. '/attribute none', '/attribute clear', '/attribute')
    if len(parts) == 1 and cmd_name in ("attribute", "--attribute"):
        state["attributes"] = []
        state["view_mode"] = "table"
        return True, None
    if len(parts) == 2 and cmd_name in ("attribute", "--attribute") and parts[1].lower() in ("none", "clear"):
        state["attributes"] = []
        state["view_mode"] = "table"
        return True, None

    if len(parts) == 1 and cmd_name in ("domain", "--domain"):
        state["domains"] = []
        state["view_mode"] = "table"
        return True, None
    if len(parts) == 2 and cmd_name in ("domain", "--domain") and parts[1].lower() in ("none", "clear"):
        state["domains"] = []
        state["view_mode"] = "table"
        return True, None

    if len(parts) == 1 and cmd_name in ("configuration", "--configuration"):
        state["configurations"] = []
        state["view_mode"] = "table"
        return True, None
    if len(parts) == 2 and cmd_name in ("configuration", "--configuration") and parts[1].lower() in ("none", "clear"):
        state["configurations"] = []
        state["view_mode"] = "table"
        return True, None

    if len(parts) == 2 and cmd_name in ("highlight", "--highlight") and parts[1].lower() in ("none", "clear", "off"):
        state["highlight"] = None
        state["view_mode"] = "table"
        return True, None

    # Normalize command to CLI parser structure
    normalized_parts = []
    for i, part in enumerate(parts):
        if i == 0:
            if not part.startswith("-"):
                normalized_parts.append(f"--{part}")
            else:
                normalized_parts.append(part)
        else:
            normalized_parts.append(part)

    from .cli import build_tui_command_parser
    parser = build_tui_command_parser()
    try:
        args = parser.parse_args(normalized_parts)
    except argparse.ArgumentError as err:
        return False, str(err)
    except Exception as err:
        return False, str(err)

    # Apply explicit namespace overrides to state
    from .cli import _split_values

    if "--attribute" in normalized_parts:
        state["attributes"] = _split_values(getattr(args, "attribute", None))
    if "--domain" in normalized_parts:
        state["domains"] = _split_values(getattr(args, "domain", None))
    if "--configuration" in normalized_parts:
        state["configurations"] = _split_values(getattr(args, "configuration", None))
    if "--errors" in normalized_parts:
        if "errors" in state:
            state["errors"] = not state["errors"]
        else:
            state["errors"] = True
    if "--summary" in normalized_parts:
        if "summary" in state:
            state["summary"] = not state["summary"]
        else:
            state["summary"] = True
    if "--highlight" in normalized_parts:
        state["highlight"] = getattr(args, "highlight", None)

    state["view_mode"] = "table"
    return True, None



def parse_ansi_to_curses_segments(line: str) -> list[tuple[str, int]]:
    segments: list[tuple[str, int]] = []
    pos = 0
    current_attr = curses.A_NORMAL

    def get_color_pair(code: int) -> int:
        if not curses.has_colors():
            return 0
        if code in (36, 96):
            return curses.color_pair(1)
        elif code in (35, 95):
            return curses.color_pair(2)
        elif code in (33, 93):
            return curses.color_pair(3)
        elif code in (32, 92):
            return curses.color_pair(4)
        elif code in (34, 94):
            return curses.color_pair(5)
        elif code in (31, 91):
            return curses.color_pair(6)
        return 0

    for match in ANSI_RE.finditer(line):
        text = line[pos:match.start()]
        if text:
            segments.append((text, current_attr))

        code_str = match.group(1)
        if not code_str or code_str == "0":
            current_attr = curses.A_NORMAL
        else:
            codes = [int(c) for c in code_str.split(";") if c.isdigit()]
            for code in codes:
                if code == 0:
                    current_attr = curses.A_NORMAL
                elif code == 1:
                    current_attr |= curses.A_BOLD
                elif code == 2:
                    current_attr |= curses.A_DIM
                elif code == 4:
                    current_attr |= curses.A_UNDERLINE
                elif (30 <= code <= 37) or (90 <= code <= 97):
                    current_attr &= ~curses.A_COLOR
                    current_attr |= get_color_pair(code)

        pos = match.end()

    text = line[pos:]
    if text:
        segments.append((text, current_attr))

    return segments


def _generate_help_text() -> str:
    return (
        "\033[1;36m# Interactive Help\033[0m\n\n"
        "\033[1mNavigation Keys:\033[0m\n"
        "  Up Arrow / k       Scroll table up by 1 line\n"
        "  Down Arrow / j     Scroll table down by 1 line\n"
        "  Left Arrow / h     Scroll table left by 4 columns\n"
        "  Right Arrow / l    Scroll table right by 4 columns\n"
        "  PageUp / b         Scroll table up by 1 screen\n"
        "  PageDown / f       Scroll table down by 1 screen\n"
        "  Home / g           Scroll to the top of the table\n"
        "  End / G            Scroll to the bottom of the table\n"
        "  /                  Open the command prompt\n"
        "  q                  Quit the TUI\n\n"
        "\033[1mCommands (Type / to enter):\033[0m\n"
        "  attribute [NAME]   Select attribute table(s) to print (space/comma separated)\n"
        "  attribute clear    Reset attribute selection back to summary\n"
        "  domain [NAME ...]  Select domain(s) for per-domain tables\n"
        "  domain clear       Reset domain selection\n"
        "  configuration [C]  Keep only the selected configuration(s) (by name or 1-based index)\n"
        "  configuration clear Reset configuration filtering\n"
        "  errors             Toggle unexplained errors\n"
        "  summary            Toggle summary table display\n"
        "  highlight [max|min]Highlight row-wise numeric maxima/minima\n"
        "  highlight off/none Clear extrema highlighting\n"
        "  merge STRING D1 D2 Merge domains D1, D2... into STRING and combine results\n"
        "  merge clear/none   Clear all active merges\n"
        "  list               List available attributes, configurations, and domains\n"
        "  help / ?           Show this help information\n"
        "  tex <filename>     Export current view as LaTeX tables\n"
        "  quit               Quit the TUI\n\n"
        "\033[2mPress any key to return to the table view.\033[0m"
    )


def _generate_list_text(report: LabReport) -> str:
    attributes = sorted(list(report.attribute_names()))
    configurations = get_report_configurations(report)
    domains = get_report_domains(report)

    lines = [
        "\033[1;36m# Report Contents\033[0m\n",
        "\033[1mAttributes:\033[0m",
    ]
    for attr in attributes:
        lines.append(f"  * {attr}")

    lines.append("\n\033[1mConfigurations:\033[0m")
    for i, config in enumerate(configurations, start=1):
        lines.append(f"  * {i}: {config}")

    lines.append("\n\033[1mDomains:\033[0m")
    for domain in domains:
        lines.append(f"  * {domain}")

    lines.append(
        "\n\033[2mUse command prompt filters to inspect. E.g., /attribute coverage or /configuration 1 or /domain blocksworld\033[0m"
    )
    lines.append("\033[2mPress any key to return to the table view.\033[0m")
    return "\n".join(lines)


def get_report_domains(report: LabReport) -> list[str]:
    domains = set()
    skipped = {"unexplained-errors", "info", "summary"}
    for section_id in report.tables:
        if section_id in skipped:
            continue
        if "-" in section_id:
            parts = section_id.split("-", 1)
            domains.add(parts[1])
    return sorted(list(domains))


def escape_latex(text: str) -> str:
    text = text.replace("\n", " ")
    mapping = {
        "\\": "\\textbackslash{}",
        "{": "\\{",
        "}": "\\}",
        "%": "\\%",
        "&": "\\&",
        "_": "\\_",
        "#": "\\#",
        "$": "\\$",
        "^": "\\^{}",
        "~": "\\~{}",
        "<": "\\textless{}",
        ">": "\\textgreater{}",
        "|": "\\textbar{}",
    }
    return "".join(mapping.get(c, c) for c in text)


def _is_numeric_str(val: str) -> bool:
    try:
        float(val)
        return True
    except ValueError:
        return False


def _get_clean_errors_table(table: Table) -> Table:
    if len(table.rows) <= 1:
        return table
    headers = list(table.rows[0])
    wanted = ["algorithm", "domain", "problem", "error", "planner_wall_clock_time", "node", "run_dir"]
    indexes = {}
    for name in wanted:
        if name in headers:
            indexes[name] = headers.index(name)
            
    message_index = 0
    rows = [["#", "domain", "problem", "error", "time", "node", "run_dir", "message"]]
    from .render import _row_value, _summarize_error
    for index, row in enumerate(table.rows[1:], start=1):
        rows.append(
            [
                str(index),
                _row_value(row, indexes.get("domain")),
                _row_value(row, indexes.get("problem")),
                _row_value(row, indexes.get("error")),
                _row_value(row, indexes.get("planner_wall_clock_time")),
                _row_value(row, indexes.get("node")),
                _row_value(row, indexes.get("run_dir")),
                _summarize_error(_row_value(row, message_index)),
            ]
        )
    from .parser import Table as ParserTable
    return ParserTable("unexplained-errors", tuple(tuple(row) for row in rows))


def export_to_latex(tables: list[Table], highlight: str | None = None) -> str:
    lines = [
        "% Auto-generated by labview",
        "% Please include \\usepackage{booktabs} in your LaTeX document preamble.",
        ""
    ]
    for table in tables:
        current_table = table
        if table.section_id == "unexplained-errors":
            current_table = _get_clean_errors_table(table)
            
        if current_table.empty:
            continue
            
        rows = current_table.rows
        num_cols = len(rows[0])
        
        alignments = []
        for col_idx in range(num_cols):
            is_numeric = True
            for row in rows[1:]:
                if col_idx < len(row):
                    val = row[col_idx].strip()
                    if val and not _is_numeric_str(val):
                        is_numeric = False
                        break
            alignments.append("r" if is_numeric else "l")
        col_spec = "".join(alignments)
        
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")
        escaped_title = escape_latex(current_table.title)
        lines.append(f"\\caption{{{escaped_title}}}")
        lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
        lines.append("\\toprule")
        
        header_row = rows[0]
        escaped_headers = [escape_latex(h) for h in header_row]
        lines.append(" & ".join(escaped_headers) + " \\\\")
        lines.append("\\midrule")
        
        for row_idx, row in enumerate(rows[1:], start=1):
            row_cells = list(row)
            highlight_cols = []
            if highlight in ("max", "min"):
                from .render import _highlight_columns
                highlight_cols = _highlight_columns(row_cells, highlight)
                
            escaped_cells = []
            for col_idx, cell in enumerate(row_cells):
                escaped_val = escape_latex(cell)
                if col_idx in highlight_cols:
                    escaped_cells.append(f"\\textbf{{{escaped_val}}}")
                else:
                    escaped_cells.append(escaped_val)
                    
            lines.append(" & ".join(escaped_cells) + " \\\\")
            
        lines.append("\\bottomrule")
        lines.append("\\end{tabular}")
        lines.append("\\end{table}")
        lines.append("")
        
    return "\n".join(lines)


def get_report_configurations(report: LabReport) -> list[str]:
    configs = set()
    summary_table = report.get_table("summary")
    if summary_table and len(summary_table.rows) > 0:
        for cell in summary_table.rows[0][1:]:
            if cell:
                configs.add(cell)
    for table in report.tables.values():
        if table.section_id == "unexplained-errors":
            if len(table.rows) > 0 and "algorithm" in table.rows[0]:
                algo_idx = table.rows[0].index("algorithm")
                for row in table.rows[1:]:
                    if algo_idx < len(row) and row[algo_idx]:
                        configs.add(row[algo_idx])
        elif table.section_id == "info":
            continue
        elif len(table.rows) > 0:
            for cell in table.rows[0][1:]:
                if cell:
                    configs.add(cell)
    return sorted(list(configs))


def _apply_merges_to_table(table: Table, merges: list[dict]) -> Table:
    if len(table.rows) < 2 or table.section_id in ("unexplained-errors", "info", "summary") or "-" in table.section_id:
        return table

    current_rows = list(table.rows)
    for merge in merges:
        name = merge["name"]
        domains_to_merge = {d.strip().lower() for d in merge["domains"]}
        
        has_summary = len(current_rows) > 2
        domain_rows_limit = len(current_rows) - 1 if has_summary else len(current_rows)
        
        matching_indices = []
        merged_rows_data = []
        
        def get_base_domain(label: str) -> str:
            return label.split(" (")[0].strip()

        for idx in range(1, domain_rows_limit):
            row_label = current_rows[idx][0]
            base_domain = get_base_domain(row_label).lower()
            if base_domain in domains_to_merge:
                matching_indices.append(idx)
                
                n_j = 1
                if " (" in row_label and row_label.endswith(")"):
                    try:
                        parts = row_label.split(" (")
                        n_str = parts[-1][:-1]
                        n_j = int(n_str)
                    except ValueError:
                        pass
                
                merged_rows_data.append((n_j, list(current_rows[idx][1:])))
                
        if not matching_indices:
            continue
            
        operation = "sum"
        if has_summary:
            summary_label = current_rows[-1][0].lower()
            if "geometric" in summary_label or "geomean" in summary_label:
                operation = "geomean"
            elif "sum" in summary_label:
                operation = "sum"
            elif "mean" in summary_label or "average" in summary_label:
                operation = "mean"
            elif "min" in summary_label:
                operation = "min"
            elif "max" in summary_label:
                operation = "max"

        combined_vals = []
        num_cols = len(current_rows[0])
        for col_idx in range(1, num_cols):
            valid_pairs = []
            for n_j, row_vals in merged_rows_data:
                if col_idx - 1 < len(row_vals):
                    val_str = row_vals[col_idx - 1]
                    try:
                        val_float = float(val_str)
                        valid_pairs.append((n_j, val_float))
                    except ValueError:
                        pass
            
            if not valid_pairs:
                raw_vals = [r[col_idx - 1] for _, r in merged_rows_data if col_idx - 1 < len(r)]
                non_empty = [rv for rv in raw_vals if rv and rv != "?"]
                combined_vals.append(non_empty[0] if non_empty else "?")
                continue
                
            if operation == "sum":
                ans = sum(val for _, val in valid_pairs)
            elif operation == "mean":
                total_n = sum(n for n, _ in valid_pairs)
                if total_n > 0:
                    ans = sum(val * n for n, val in valid_pairs) / total_n
                else:
                    ans = sum(val for _, val in valid_pairs) / len(valid_pairs)
            elif operation == "geomean":
                import math
                total_n = sum(n for n, _ in valid_pairs)
                if total_n > 0:
                    log_sum = 0.0
                    has_zero_or_neg = False
                    for n, val in valid_pairs:
                        if val <= 0:
                            has_zero_or_neg = True
                            break
                        log_sum += n * math.log(val)
                    if has_zero_or_neg:
                        ans = 0.0
                    else:
                        ans = math.exp(log_sum / total_n)
                else:
                    ans = 0.0
            elif operation == "min":
                ans = min(val for _, val in valid_pairs)
            elif operation == "max":
                ans = max(val for _, val in valid_pairs)
            else:
                ans = sum(val for _, val in valid_pairs)
                
            if ans.is_integer():
                combined_vals.append(str(int(ans)))
            else:
                formatted = f"{ans:.4f}".rstrip("0").rstrip(".")
                combined_vals.append(formatted)
                
        total_problems = sum(n_j for n_j, _ in merged_rows_data)
        new_row_label = f"{name} ({total_problems})" if total_problems > 0 else name
        new_row = tuple([new_row_label] + combined_vals)

        remaining_rows = []
        for idx, row in enumerate(current_rows):
            if idx not in matching_indices:
                remaining_rows.append(row)

        if has_summary and len(remaining_rows) > 1:
            next_rows = remaining_rows[:-1] + [new_row] + [remaining_rows[-1]]
        else:
            next_rows = remaining_rows + [new_row]
        current_rows = next_rows

    return Table(table.section_id, tuple(current_rows))
