# labview

`labview` is a small terminal viewer for
[Lab](https://lab.readthedocs.io/en/stable/) HTML reports.

It extracts the tables Lab already writes into the report and renders them as
readable terminal tables. This is useful when you want to inspect experiment
results over SSH, in CI logs, or without opening a browser.

## Features

- Print the summary table by default.
- Print selected attribute tables such as `coverage`, `search_time`, or
  `total_time`.
- Print per-domain tables for selected attributes.
- List all available report attributes.
- Show unexplained errors as a compact terminal table.
- Page long output through the system pager.
- Color table headers and the algorithm legend in terminals.
- Highlight row-wise numeric minima or maxima.
- No runtime dependencies.

## Installation

### With uv

Install directly from a local checkout:

```bash
uv tool install .
```

Then run:

```bash
labview path/to/report.html
```

For development, install the package in editable mode:

```bash
uv venv
uv pip install -e .
```

After that, edits to `src/labview` are picked up by the installed `labview`
command.

### With pip

From a local checkout:

```bash
python -m pip install .
```

For editable development installs:

```bash
python -m pip install -e .
```

## Usage

Print the summary table:

```bash
labview report.html
```

List available attributes:

```bash
labview report.html --list-attributes
```

Print selected attribute tables:

```bash
labview report.html --attribute coverage search_time
labview report.html --attribute coverage,search_time
```

Print per-domain tables for selected attributes:

```bash
labview report.html --attribute coverage --domain blocksworld ferry
```

Always print the summary first:

```bash
labview report.html --summary --attribute coverage --errors
```

Show unexplained errors:

```bash
labview report.html --errors
```

Highlight row-wise extrema:

```bash
labview report.html --attribute coverage --highlight max
labview report.html --attribute search_time --highlight min
```

Page long output:

```bash
labview report.html --attribute coverage --domain blocksworld --paging
```

Control colors:

```bash
labview report.html --color=always
labview report.html --color=never
```

Colors are enabled automatically for terminal output and disabled for redirected
output. `NO_COLOR` is respected.

## Options

| Option | Description |
| --- | --- |
| `report` | Path to a Lab HTML report. |
| `-a`, `--attribute NAME [NAME ...]` | Print one or more attribute tables. Values can be space-separated or comma-separated. |
| `-d`, `--domain NAME [NAME ...]` | Also print per-domain tables for each selected attribute. Requires `--attribute`. |
| `-e`, `--errors` | Print unexplained errors before the selected report tables. |
| `--summary` | Print the summary table at the top, even when attributes are selected. |
| `--list-attributes` | List available top-level attribute tables and exit. |
| `--highlight {max,min}` | Bold and underline the row-wise maximum or minimum numeric values. Ties are highlighted together. |
| `-p`, `--paging` | Send output through the system pager. |
| `--color {auto,always,never}` | Control ANSI colors. The default is `auto`. |

## Development

Run the test suite:

```bash
uv run python -m unittest discover -s tests -v
```

Check Python syntax:

```bash
uv run python -m compileall -q src tests
```

Build the package:

```bash
uv build
```

## Notes

`labview` expects the report structure produced by Lab's HTML reports: a set of
`<section id="...">` blocks containing tables. It intentionally does not try to
recompute experiment statistics; it only renders the data already present in the
HTML report.
