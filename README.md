# Nonogram / Picross Solver (Tkinter)
![简体中文](./README_ZH.md)
---

A local desktop Nonogram (Picross) solver with a Tkinter GUI. Enter row and column clues, solve using logic propagation plus backtracking, and save/load puzzles as JSON. Designed for Python 3.10+ with no third-party dependencies.

## Features

- GUI for editing row/column clues and visualizing the grid
- Left-click cycles a cell through unknown/filled/empty, right-click sets empty
- Logic propagation (constraint intersection) + DFS backtracking
- Detects no-solution / unique-solution / multiple-solution cases
- Step mode: one propagation pass for incremental solving
- Stop button to cancel long solves (threaded, UI stays responsive)
- JSON open/save with current grid state

## Requirements

- Python 3.10+
- Tkinter (ships with standard Python on most platforms)

## Quick Start

```bash
python main.py
```

Optional: open the sample puzzle at `examples/sample_10x10.json`.

## UI Guide

- New: create a new puzzle size
- Open/Save: load or persist a JSON puzzle file
- Solve: full solve (propagation + DFS), reports status
- Step: one propagation pass (no backtracking)
- Stop: cancel a running solve
- Reset: clear the grid to all unknown

### Editing clues

- Double-click a row/column hint area to edit that line.
- Use `.` (dot) as the separator when typing clues, for example:
  - `3.1.2` means blocks of 3, 1, and 2
  - empty input means no filled cells
- Dot separators are used to make numeric keypad input faster.
- Display formatting uses spaces (rows) or line breaks (columns); dots are input-only.

### Grid interaction

- Left-click cycles unknown (-1) -> filled (1) -> empty (0)
- Right-click sets empty (0)

## Solver Notes

The solver works in two phases:

1) **Logic propagation**
   - For each row/column, generate all line patterns that match the clue.
   - Filter patterns against current known cells.
   - Intersect all valid patterns to determine forced cells.

2) **Backtracking (DFS)**
   - If propagation stalls, choose the row/column with the fewest candidates.
   - Branch on candidate patterns, continue propagation.
   - Stop after finding two solutions to report "multiple solutions".

Solve can be interrupted at any time with Stop.

### Step vs Solve

- Step runs exactly one propagation pass: it generates valid line patterns for all rows and columns, intersects them, and applies any forced cells.
- Solve repeats propagation until it cannot make further changes, then switches to backtracking search. It chooses a row/column with the fewest valid candidates, branches on a candidate, and continues propagation in each branch. The search stops after 2 solutions to report "multiple solutions".

## JSON File Format

```json
{
  "width": 10,
  "height": 10,
  "row_clues": [[3], [1,1], [], ...],
  "col_clues": [[2], [1,1], [], ...],
  "grid": [[-1, -1, 1, 0, ...], ...]
}
```

Grid values:
- `-1` = unknown
- `0` = empty
- `1` = filled

## Project Structure

```
nonogram/
  __init__.py
  model.py   # data model + JSON IO
  solver.py  # propagation + backtracking solver
  gui.py     # Tkinter UI
main.py      # app entry point
README.md
examples/
  sample_10x10.json
```

## Performance

- Typical 5x5 to 25x25 puzzles solve quickly.
- Hard puzzles may require deeper search; use Stop to cancel.

## Exporting an Image

This project does not include a built-in PNG export. You can:
- Use a screenshot tool, or
- Add Pillow yourself and export from the canvas

## Publish to GitHub

From the project root:

```bash
git init
git add .
git commit -m "Initial commit"
```

Create a new repository on GitHub, then:

```bash
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

## Troubleshooting

- If Solve reports "no solution", verify the clues and current grid state.
- If Solve reports "multiple solutions", the puzzle is ambiguous.
- If it is slow, try Step to see propagation progress or Stop to cancel.
