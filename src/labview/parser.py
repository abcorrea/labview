from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Cell:
    text: str
    header: bool = False
    rowspan: int = 1
    colspan: int = 1


@dataclass(frozen=True)
class Table:
    section_id: str
    rows: tuple[tuple[str, ...], ...]

    @property
    def title(self) -> str:
        return self.section_id

    @property
    def empty(self) -> bool:
        return not self.rows


class LabReport:
    def __init__(self, tables: dict[str, Table]) -> None:
        self.tables = tables

    @classmethod
    def from_file(cls, path: Path) -> "LabReport":
        parser = _LabHTMLParser()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        parser.close()
        return cls(parser.tables)

    def get_table(self, section_id: str) -> Table | None:
        return self.tables.get(section_id)

    def require_table(self, section_id: str) -> Table:
        table = self.get_table(section_id)
        if table is None:
            available = ", ".join(sorted(self.attribute_names())[:20])
            raise KeyError(
                f"Report has no table '{section_id}'."
                + (f" Available attributes include: {available}" if available else "")
            )
        return table

    def attribute_names(self) -> Iterable[str]:
        skipped = {"unexplained-errors", "info", "summary"}
        for section_id in self.tables:
            if section_id not in skipped and "-" not in section_id:
                yield section_id


class _LabHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: dict[str, Table] = {}
        self._section_id: str | None = None
        self._capture_table = False
        self._captured_sections: set[str] = set()
        self._raw_rows: list[list[Cell]] = []
        self._raw_row: list[Cell] | None = None
        self._cell_parts: list[str] | None = None
        self._cell_header = False
        self._cell_rowspan = 1
        self._cell_colspan = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "section":
            self._section_id = attr_map.get("id")
            return

        if tag == "table" and self._section_id and self._section_id not in self._captured_sections:
            self._capture_table = True
            self._raw_rows = []
            return

        if not self._capture_table:
            return

        if tag == "tr":
            self._raw_row = []
        elif tag in {"td", "th"} and self._raw_row is not None:
            self._cell_parts = []
            self._cell_header = tag == "th"
            self._cell_rowspan = _positive_int(attr_map.get("rowspan"), default=1)
            self._cell_colspan = _positive_int(attr_map.get("colspan"), default=1)
        elif tag == "br" and self._cell_parts is not None:
            self._cell_parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and self._cell_parts is not None:
            self._cell_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_table:
            return

        if tag in {"td", "th"} and self._raw_row is not None and self._cell_parts is not None:
            self._raw_row.append(
                Cell(
                    text=_clean_text("".join(self._cell_parts)),
                    header=self._cell_header,
                    rowspan=self._cell_rowspan,
                    colspan=self._cell_colspan,
                )
            )
            self._cell_parts = None
        elif tag == "tr" and self._raw_row is not None:
            self._raw_rows.append(self._raw_row)
            self._raw_row = None
        elif tag == "table" and self._section_id is not None:
            self.tables[self._section_id] = Table(
                section_id=self._section_id,
                rows=tuple(tuple(row) for row in _expand_spans(self._raw_rows)),
            )
            self._captured_sections.add(self._section_id)
            self._capture_table = False
            self._raw_rows = []


def _positive_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(parsed, 1)


def _clean_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _expand_spans(raw_rows: list[list[Cell]]) -> list[list[str]]:
    rows: list[list[str]] = []
    active: dict[int, tuple[int, str]] = {}

    for raw_row in raw_rows:
        row: list[str] = []
        col = 0

        def fill_active() -> None:
            nonlocal col
            while col in active:
                remaining, value = active[col]
                row.append(value)
                if remaining <= 1:
                    del active[col]
                else:
                    active[col] = (remaining - 1, value)
                col += 1

        fill_active()
        for cell in raw_row:
            fill_active()
            for offset in range(cell.colspan):
                value = cell.text if offset == 0 else ""
                row.append(value)
                if cell.rowspan > 1:
                    active[col] = (cell.rowspan - 1, value)
                col += 1
        fill_active()
        rows.append(row)

    if not rows:
        return rows

    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]
