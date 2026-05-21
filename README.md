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
- Filter tables to selected configurations by name or by 1-based index.
- List all available report attributes.
- Show unexplained errors as a compact terminal table.
- Page long output through the system pager.
- Color table headers and the algorithm legend in terminals.
- Highlight row-wise numeric minima or maxima.
- **Interactive TUI Mode** (via `--tui` / `-t`):
  - Viewport navigation (Arrow keys, Page Up/Down, Vim navigation keys).
  - Forward-slash command entry (`/`) to dynamically update the view.
  - Cycle-based tab autocompletion for commands, attributes, configurations, and domains.
  - Configuration filtering by number (e.g. `/configuration 1` translates to the first configuration name).
  - Dynamic domain merging (`/merge STRING domain1 domain2 ...`) with correct aggregation (weighted sum, means, mins, maxes) placed immediately above the table summary row.
  - LaTeX export of the active view (`/tex filename.tex`).
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

Filter configurations by name or by their 1-based table position:

```bash
labview report.html --attribute coverage --configuration lama
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

## Interactive TUI Mode

Launch the interactive Curses TUI:

```bash
labview report.html --tui
```

### Controls
- **Up/Down / Vim `k`/`j`**: Scroll table viewport by one line.
- **Page Up/Down / Vim `Ctrl-u`/`Ctrl-d`**: Scroll by full screen.
- **Home/End / Vim `g`/`G`**: Scroll to top/bottom.
- **`/`**: Open command prompt to input interactive options.
- **`q`**: Return to table view from help/list views, or exit when in the table view.

### Curses Slash Commands (Press `/` to enter)
- `/attribute [attr1,attr2,...]` or `/attribute clear`: Show specified attribute tables, or clear them.
- `/domain [domain1,domain2,...]` or `/domain none`: Limit to or show domain details.
- `/configuration [config1,config2,...]` or `/configuration none`: Filter configuration columns by name or number (e.g. `1,2`).
- `/highlight [max|min|off]`: Toggle row-wise numeric minima/maxima highlight.
- `/summary`: Toggle summary table display.
- `/errors`: Toggle unexplained errors table.
- `/merge STRING d1 d2 ...`: Group domains `d1`, `d2`, etc. into a single row named `STRING`. Combines values mathematically based on the summary row operation (e.g. weighted mean/geomean/sum), and places the row immediately on top of the last summary row.
- `/merge clear` or `/merge none`: Clear all active merges.
- `/list`: Display all available configurations, attributes, and domains.
- `/tex <filename>`: Export the current active filtered and merged view as LaTeX tables.
- `/quit` or `/q`: Exit the viewer.
- `/help` or `/?`: Show the help page.

## Options

| Option | Description |
| --- | --- |
| `report` | Path to a Lab HTML report. |
| `-t`, `--tui` | Launch the interactive Terminal User Interface (TUI) mode. |
| `-a`, `--attribute NAME [NAME ...]` | Print one or more attribute tables. Values can be space-separated or comma-separated. |
| `-d`, `--domain NAME [NAME ...]` | Also print per-domain tables for each selected attribute. Requires `--attribute`. |
| `-c`, `--configuration NAME_OR_INDEX [NAME_OR_INDEX ...]` | Keep only the selected configurations. Values can be configuration names or 1-based configuration indexes, and can be space-separated or comma-separated. |
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
