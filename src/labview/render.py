from __future__ import annotations

import shutil
import textwrap

from .parser import Table


def render_sections(
    tables: list[Table],
    *,
    width: int | None = None,
    color: bool = False,
    highlight: str | None = None,
) -> str:
    width = width or shutil.get_terminal_size(fallback=(120, 40)).columns
    rendered = []
    for table in tables:
        rendered.append(render_table(table, width=width, color=color, highlight=highlight))
    return "\n\n".join(part for part in rendered if part)


def render_table(table: Table, *, width: int, color: bool = False, highlight: str | None = None) -> str:
    if table.section_id == "unexplained-errors":
        return _render_errors(table, width=width, color=color)
    if table.empty:
        return f"{_style(table.title, _CYAN_BOLD, color)}\n(no rows)"

    rows = [list(row) for row in table.rows]
    rows, legend = _compact_algorithm_headers(rows, width)
    col_widths = _column_widths(rows, width)
    styles = _cell_styles(rows, color=color, highlight=highlight)
    rendered_rows = [
        _render_row(row, col_widths, styles[index], style_enabled=color)
        for index, row in enumerate(rows)
    ]
    rule = _rule(col_widths)

    lines = [_style(table.title, _CYAN_BOLD, color), _style(rule, _DIM, color)]
    for index, row_lines in enumerate(rendered_rows):
        lines.extend(row_lines)
        if index == 0:
            lines.append(_style(rule, _DIM, color))
    lines.append(_style(rule, _DIM, color))
    if legend:
        lines.extend(["", *_render_legend(legend, color=color)])
    return "\n".join(lines)


def _compact_algorithm_headers(rows: list[list[str]], width: int) -> tuple[list[list[str]], list[str]]:
    if not rows or len(rows[0]) < 4:
        return rows, []

    header = rows[0]
    estimated = sum(max(3, min(len(cell), 30)) for cell in header) + (3 * len(header)) + 1
    if estimated <= width:
        return rows, []

    compact = [header[0], *[f"A{i}" for i in range(1, len(header))]]
    legend = ["Columns:"]
    legend.extend(f"  A{i}: {value}" for i, value in enumerate(header[1:], start=1))
    return [compact, *rows[1:]], legend


def _column_widths(rows: list[list[str]], total_width: int) -> list[int]:
    columns = max(len(row) for row in rows)
    natural = [
        max(_display_len(line) for row in rows for line in _cell_lines(row[col] if col < len(row) else ""))
        for col in range(columns)
    ]
    widths = [min(max(value, 3), 28) for value in natural]

    max_table_width = max(total_width, 40)
    while sum(widths) + 3 * columns + 1 > max_table_width and max(widths) > 6:
        largest = max(range(columns), key=lambda index: widths[index])
        widths[largest] -= 1
    return widths


def _render_row(
    row: list[str],
    widths: list[int],
    styles: list[str] | None = None,
    *,
    style_enabled: bool = False,
) -> list[str]:
    styles = styles or [""] * len(widths)
    wrapped_cells = [
        _wrap_cell(row[index] if index < len(row) else "", width)
        for index, width in enumerate(widths)
    ]
    height = max(len(cell) for cell in wrapped_cells)
    lines = []
    for line_index in range(height):
        parts = []
        for cell, width in zip(wrapped_cells, widths):
            index = len(parts)
            value = cell[line_index] if line_index < len(cell) else ""
            padded = value.ljust(width)
            parts.append(_style(padded, styles[index] if index < len(styles) else "", style_enabled))
        lines.append("| " + " | ".join(parts) + " |")
    return lines


def _wrap_cell(value: str, width: int) -> list[str]:
    lines: list[str] = []
    for source_line in _cell_lines(value):
        wrapped = textwrap.wrap(
            source_line,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            placeholder="",
        )
        lines.extend(wrapped or [""])
    return lines or [""]


def _cell_lines(value: str) -> list[str]:
    return str(value).splitlines() or [""]


def _rule(widths: list[int]) -> str:
    return "+-" + "-+-".join("-" * width for width in widths) + "-+"


def _display_len(value: str) -> int:
    return len(value)


def _cell_styles(rows: list[list[str]], *, color: bool, highlight: str | None) -> list[list[str]]:
    styles: list[list[str]] = []
    for row_index, row in enumerate(rows):
        row_styles = [_base_cell_style(row_index, column_index, color) for column_index in range(len(row))]
        if highlight and row_index > 0:
            for column_index in _highlight_columns(row, highlight):
                row_styles[column_index] = _combine_styles(row_styles[column_index], _BOLD_UNDERLINE)
        styles.append(row_styles)
    return styles


def _base_cell_style(row_index: int, column_index: int, color: bool) -> str:
    style = _BOLD if row_index == 0 else ""
    if color and row_index == 0 and column_index > 0:
        style = _combine_styles(style, _algorithm_color(column_index))
    return style


def _highlight_columns(row: list[str], mode: str) -> list[int]:
    values = []
    for column_index, value in enumerate(row[1:], start=1):
        number = _parse_number(value)
        if number is not None:
            values.append((column_index, number))
    if not values:
        return []

    selected = max(number for _, number in values) if mode == "max" else min(number for _, number in values)
    return [column_index for column_index, number in values if number == selected]


def _parse_number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _render_errors(table: Table, *, width: int, color: bool = False) -> str:
    if len(table.rows) <= 1:
        return f"{_style(table.title, _RED_BOLD, color)}\n(no unexplained errors)"

    headers = list(table.rows[0])
    wanted = ["algorithm", "domain", "problem", "error", "planner_wall_clock_time", "node", "run_dir"]
    indexes = {name: headers.index(name) for name in wanted if name in headers}
    message_index = 0

    rows = [["#", "domain", "problem", "error", "time", "node", "run_dir", "message"]]
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

    compact = Table("unexplained-errors", tuple(tuple(row) for row in rows))
    rows = [list(row) for row in compact.rows]
    col_widths = _column_widths(rows, width)
    styles = _cell_styles(rows, color=color, highlight=None)
    rendered_rows = [
        _render_row(row, col_widths, styles[index], style_enabled=color)
        for index, row in enumerate(rows)
    ]
    rule = _rule(col_widths)

    lines = [_style(f"{table.title} ({len(table.rows) - 1})", _RED_BOLD, color), _style(rule, _DIM, color)]
    for index, row_lines in enumerate(rendered_rows):
        lines.extend(row_lines)
        if index == 0:
            lines.append(_style(rule, _DIM, color))
    lines.append(_style(rule, _DIM, color))
    return "\n".join(lines)


def _row_value(row: tuple[str, ...], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def _summarize_error(value: str) -> str:
    lines = [line.strip(" '[]") for line in value.splitlines()]
    lines = [line for line in lines if line and line != "run.err:"]
    if not lines:
        return ""
    for line in reversed(lines):
        if line.endswith("Error") or "Error:" in line or line.startswith("SystemError"):
            return line
    return lines[-1]


_RESET = "\033[0m"
_BOLD = "\033[1m"
_UNDERLINE = "\033[4m"
_BOLD_UNDERLINE = _BOLD + _UNDERLINE
_DIM = "\033[2m"
_CYAN_BOLD = "\033[1;36m"
_RED_BOLD = "\033[1;31m"
_ALGORITHM_COLORS = [
    "\033[36m",
    "\033[35m",
    "\033[33m",
    "\033[32m",
    "\033[34m",
    "\033[31m",
    "\033[96m",
    "\033[95m",
    "\033[93m",
    "\033[92m",
    "\033[94m",
    "\033[91m",
]


def _style(value: str, code: str, enabled: bool) -> str:
    if not enabled or not code:
        return value
    return f"{code}{value}{_RESET}"


def _algorithm_color(column_index: int) -> str:
    return _ALGORITHM_COLORS[(column_index - 1) % len(_ALGORITHM_COLORS)]


def _combine_styles(*styles: str) -> str:
    return "".join(style for style in styles if style)


def _render_legend(legend: list[str], *, color: bool) -> list[str]:
    rendered = []
    for index, line in enumerate(legend):
        if index == 0:
            rendered.append(_style(line, _DIM, color))
        else:
            rendered.append(_style(line, _combine_styles(_DIM, _algorithm_color(index)), color))
    return rendered
