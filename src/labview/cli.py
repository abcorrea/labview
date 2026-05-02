from __future__ import annotations

import argparse
import os
import pydoc
import sys
from pathlib import Path

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
    except KeyError as err:
        parser.error(str(err).strip("'"))

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
