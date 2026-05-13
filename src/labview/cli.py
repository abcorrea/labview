from __future__ import annotations

import argparse
import os
import pydoc
import sys
from pathlib import Path
from typing import Iterable

from .parser import LabReport, Table
from .render import render_sections


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.is_file():
        parser.error(f"report does not exist: {report_path}")

    attributes = _split_values(args.attribute)
    domains = _split_values(args.domain)
    configurations = _split_values(args.configuration)

    report = LabReport.from_file(report_path)

    if args.list_attributes:
        print(_format_attributes(report))
        return 0

    if domains and not attributes:
        parser.error("--domain requires --attribute")

    try:
        tables = _select_tables(
            report,
            attributes=attributes,
            domains=domains,
            include_errors=args.errors,
            include_summary=args.summary,
        )
        if configurations:
            tables = _filter_configurations(tables, configurations)
    except KeyError as err:
        parser.error(str(err).strip("'"))
    except ValueError as err:
        parser.error(str(err))

    output = render_sections(tables, color=_use_color(args.color), highlight=args.highlight)
    if args.paging:
        pydoc.pager(output)
    else:
        print(output)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="labview",
        description="Print selected tables from a Lab HTML report.",
    )
    parser.add_argument("report", help="path to a Lab HTML report")
    parser.add_argument(
        "-a",
        "--attribute",
        nargs="+",
        help="attribute table names to print, for example: coverage search_time",
    )
    parser.add_argument(
        "-d",
        "--domain",
        nargs="+",
        help="domain names whose per-domain tables should be printed for each attribute",
    )
    parser.add_argument(
        "-c",
        "--configuration",
        nargs="+",
        help=(
            "configuration names or 1-based configuration indexes to keep, "
            "for example: lama 2"
        ),
    )
    parser.add_argument(
        "-e",
        "--errors",
        action="store_true",
        help="print unexplained errors before the selected report tables",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print the summary table at the top, even when attributes are selected",
    )
    parser.add_argument(
        "-p",
        "--paging",
        action="store_true",
        help="page the output with the system pager",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colorize output: auto, always, or never",
    )
    parser.add_argument(
        "--highlight",
        choices=["max", "min"],
        help="highlight row-wise maximum or minimum numeric values",
    )
    parser.add_argument(
        "--list-attributes",
        action="store_true",
        help="list available attribute tables and exit",
    )
    return parser


def _select_tables(
    report: LabReport,
    *,
    attributes: list[str],
    domains: list[str],
    include_errors: bool,
    include_summary: bool = False,
) -> list[Table]:
    tables: list[Table] = []

    if include_summary:
        _append_table(tables, report.require_table("summary"))

    if include_errors:
        _append_table(tables, report.require_table("unexplained-errors"))

    if not attributes:
        if not include_summary:
            _append_table(tables, report.require_table("summary"))
        return tables

    for attribute in attributes:
        _append_table(tables, report.require_table(attribute))
        for domain in domains:
            _append_table(tables, report.require_table(f"{attribute}-{domain}"))

    return tables


def _split_values(values: list[str] | None) -> list[str]:
    if not values:
        return []
    result = []
    for value in values:
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return result


def _filter_configurations(tables: list[Table], configurations: list[str]) -> list[Table]:
    return [_filter_table_configurations(table, configurations) for table in tables]


def _filter_table_configurations(table: Table, configurations: list[str]) -> Table:
    if table.empty:
        return table

    header = table.rows[0]
    if _has_algorithm_rows(table):
        return _filter_algorithm_rows(table, configurations)

    column_indexes = _selected_configuration_columns(header, configurations, table.section_id)
    rows = tuple(tuple(_cell_value(row, index) for index in column_indexes) for row in table.rows)
    return Table(table.section_id, rows)


def _has_algorithm_rows(table: Table) -> bool:
    return table.section_id == "unexplained-errors" and "algorithm" in table.rows[0]


def _filter_algorithm_rows(table: Table, configurations: list[str]) -> Table:
    header = table.rows[0]
    algorithm_index = header.index("algorithm")
    algorithms = _ordered_values(_cell_value(row, algorithm_index) for row in table.rows[1:])
    wanted = _selected_configuration_names(algorithms, configurations, table.section_id)
    rows = [header]
    rows.extend(row for row in table.rows[1:] if _cell_value(row, algorithm_index) in wanted)
    return Table(table.section_id, tuple(rows))


def _selected_configuration_columns(
    header: tuple[str, ...],
    configurations: list[str],
    section_id: str,
) -> list[int]:
    selected = [0]
    for index in _configuration_indexes(header, configurations, section_id):
        if index not in selected:
            selected.append(index)
    return selected


def _selected_configuration_names(
    available: list[str],
    configurations: list[str],
    section_id: str,
) -> set[str]:
    if not available:
        raise ValueError(f"Table '{section_id}' has no configurations to filter.")

    selected = []
    for configuration in configurations:
        selected.append(_resolve_configuration_name(available, configuration, section_id))
    return set(selected)


def _configuration_indexes(
    header: tuple[str, ...],
    configurations: list[str],
    section_id: str,
) -> list[int]:
    if len(header) <= 1:
        raise ValueError(f"Table '{section_id}' has no configurations to filter.")

    indexes = []
    for configuration in configurations:
        indexes.append(_resolve_configuration(header, configuration, section_id))
    return indexes


def _resolve_configuration(header: tuple[str, ...], configuration: str, section_id: str) -> int:
    if configuration.isdecimal():
        index = int(configuration)
        if 1 <= index < len(header):
            return index
        raise ValueError(
            f"Configuration index {index} is out of range for table '{section_id}'. "
            f"Valid indexes are 1..{len(header) - 1}."
        )

    try:
        return header.index(configuration, 1)
    except ValueError as err:
        available = ", ".join(header[1:])
        raise ValueError(
            f"Table '{section_id}' has no configuration '{configuration}'."
            + (f" Available configurations: {available}" if available else "")
        ) from err


def _resolve_configuration_name(available: list[str], configuration: str, section_id: str) -> str:
    if configuration.isdecimal():
        index = int(configuration)
        if 1 <= index <= len(available):
            return available[index - 1]
        raise ValueError(
            f"Configuration index {index} is out of range for table '{section_id}'. "
            f"Valid indexes are 1..{len(available)}."
        )

    if configuration in available:
        return configuration

    raise ValueError(
        f"Table '{section_id}' has no configuration '{configuration}'. "
        f"Available configurations: {', '.join(available)}"
    )


def _ordered_values(values: Iterable[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _cell_value(row: tuple[str, ...], index: int) -> str:
    if index >= len(row):
        return ""
    return row[index]


def _append_table(tables: list[Table], table: Table) -> None:
    if table.section_id not in {existing.section_id for existing in tables}:
        tables.append(table)


def _format_attributes(report: LabReport) -> str:
    attributes = list(report.attribute_names())
    if not attributes:
        return "No attribute tables found."
    return "\n".join(attributes)


def _use_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never" or "NO_COLOR" in os.environ:
        return False
    return sys.stdout.isatty()


if __name__ == "__main__":
    sys.exit(main())
