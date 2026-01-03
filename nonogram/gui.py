from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import List, Optional, Tuple

from .model import Puzzle, UNKNOWN, EMPTY, FILLED
from .solver import propagate_once, solve_nonogram


class NonogramApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nonogram Solver")
        self.geometry("1100x800")

        self.width = 10
        self.height = 10
        self.cell_size = 24

        self.row_clues: List[List[int]] = [[] for _ in range(self.height)]
        self.col_clues: List[List[int]] = [[] for _ in range(self.width)]
        self.grid: List[List[int]] = [[UNKNOWN for _ in range(self.width)] for _ in range(self.height)]

        self.stop_event = threading.Event()
        self.solve_thread: Optional[threading.Thread] = None
        self.queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._update_hint_sizes()
        self._redraw_hints()
        self._redraw_grid()
        self.after(100, self._process_queue)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="New", command=self.new_puzzle).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Open", command=self.open_puzzle).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Save", command=self.save_puzzle).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Solve", command=self.solve_puzzle).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Stop", command=self.stop_solve).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Reset", command=self.reset_grid).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Step", command=self.step_puzzle).pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Label(toolbar, text="Cell").pack(side=tk.LEFT, padx=(16, 4))
        self.cell_var = tk.IntVar(value=self.cell_size)
        cell_scale = ttk.Scale(toolbar, from_=12, to=40, orient=tk.HORIZONTAL, command=self._on_cell_scale)
        cell_scale.set(self.cell_size)
        cell_scale.pack(side=tk.LEFT, padx=4, pady=2)

        main = ttk.Frame(self)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=0)
        main.rowconfigure(0, weight=0)
        main.rowconfigure(1, weight=1)

        self.corner_frame = ttk.Frame(main)
        self.corner_frame.grid(row=0, column=0, sticky="nsew")

        self.col_hint_canvas = tk.Canvas(main, bg="white", highlightthickness=1, highlightbackground="#999999")
        self.col_hint_canvas.grid(row=0, column=1, sticky="nsew")
        self.col_hint_canvas.bind("<Double-Button-1>", self._on_edit_col_hint)

        self.row_hint_canvas = tk.Canvas(main, bg="white", highlightthickness=1, highlightbackground="#999999")
        self.row_hint_canvas.grid(row=1, column=0, sticky="nsew")
        self.row_hint_canvas.bind("<Double-Button-1>", self._on_edit_row_hint)

        self.grid_canvas = tk.Canvas(main, bg="white", highlightthickness=1, highlightbackground="#999999")
        self.grid_canvas.grid(row=1, column=1, sticky="nsew")

        self.grid_canvas.bind("<Button-1>", self._on_left_click)
        self.grid_canvas.bind("<Button-3>", self._on_right_click)
        self.grid_canvas.bind("<MouseWheel>", self._on_mouse_wheel)

        log_frame = ttk.Frame(main)
        log_frame.grid(row=0, column=2, rowspan=2, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, width=35, height=20, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def _update_hint_sizes(self) -> None:
        max_row_blocks = max(1, (self.width + 1) // 2)
        max_col_blocks = max(1, (self.height + 1) // 2)

        row_hint_width = max(70, max_row_blocks * self.cell_size)
        col_hint_height = max(40, max_col_blocks * self.cell_size)

        self.corner_frame.configure(width=row_hint_width, height=col_hint_height)
        self.corner_frame.grid_propagate(False)
        self.row_hint_canvas.configure(width=row_hint_width, height=self.height * self.cell_size)
        self.col_hint_canvas.configure(width=self.width * self.cell_size, height=col_hint_height)

    def _redraw_hints(self) -> None:
        self.row_hint_canvas.delete("all")
        self.col_hint_canvas.delete("all")

        row_width = int(self.row_hint_canvas.cget("width"))
        col_height = int(self.col_hint_canvas.cget("height"))

        for r in range(self.height):
            y = r * self.cell_size
            self.row_hint_canvas.create_line(0, y, row_width, y, fill="#e0e0e0")
        for c in range(self.width):
            x = c * self.cell_size
            self.col_hint_canvas.create_line(x, 0, x, col_height, fill="#e0e0e0")

        for r in range(self.height):
            text = " ".join(str(n) for n in self.row_clues[r])
            y = r * self.cell_size + self.cell_size / 2
            self.row_hint_canvas.create_text(
                row_width - 6,
                y,
                text=text,
                anchor="e",
            )

        for c in range(self.width):
            text = "\n".join(str(n) for n in self.col_clues[c])
            x = c * self.cell_size + self.cell_size / 2
            self.col_hint_canvas.create_text(
                x,
                col_height - 6,
                text=text,
                anchor="s",
            )

    def _redraw_grid(self) -> None:
        self.grid_canvas.delete("all")
        self.cell_items: List[List[int]] = []
        for r in range(self.height):
            row_items = []
            for c in range(self.width):
                x0 = c * self.cell_size
                y0 = r * self.cell_size
                x1 = x0 + self.cell_size
                y1 = y0 + self.cell_size
                item = self.grid_canvas.create_rectangle(
                    x0, y0, x1, y1, outline="#888888", fill=self._color_for(self.grid[r][c])
                )
                row_items.append(item)
            self.cell_items.append(row_items)
        self.grid_canvas.configure(scrollregion=(0, 0, self.width * self.cell_size, self.height * self.cell_size))
        self._update_hint_sizes()
        self._redraw_hints()

    def _color_for(self, v: int) -> str:
        if v == FILLED:
            return "#000000"
        if v == EMPTY:
            return "#ffffff"
        return "#dddddd"

    def _set_cell(self, r: int, c: int, v: int) -> None:
        self.grid[r][c] = v
        self.grid_canvas.itemconfig(self.cell_items[r][c], fill=self._color_for(v))

    def _on_left_click(self, event) -> None:
        r, c = self._event_to_cell(event)
        if r is None:
            return
        cur = self.grid[r][c]
        if cur == UNKNOWN:
            self._set_cell(r, c, FILLED)
        elif cur == FILLED:
            self._set_cell(r, c, EMPTY)
        else:
            self._set_cell(r, c, UNKNOWN)

    def _on_right_click(self, event) -> None:
        r, c = self._event_to_cell(event)
        if r is None:
            return
        self._set_cell(r, c, EMPTY)

    def _event_to_cell(self, event) -> Tuple[Optional[int], Optional[int]]:
        x = self.grid_canvas.canvasx(event.x)
        y = self.grid_canvas.canvasy(event.y)
        c = int(x // self.cell_size)
        r = int(y // self.cell_size)
        if 0 <= r < self.height and 0 <= c < self.width:
            return r, c
        return None, None

    def _on_mouse_wheel(self, event) -> None:
        if event.delta > 0:
            self._change_cell_size(1)
        else:
            self._change_cell_size(-1)

    def _on_cell_scale(self, value) -> None:
        v = int(float(value))
        self._set_cell_size(v)

    def _change_cell_size(self, delta: int) -> None:
        new_size = max(12, min(40, self.cell_size + delta))
        self._set_cell_size(new_size)

    def _set_cell_size(self, size: int) -> None:
        if size == self.cell_size:
            return
        self.cell_size = size
        self.cell_var.set(size)
        self._update_hint_sizes()
        self._redraw_hints()
        self._redraw_grid()

    def _parse_clue_text(self, text: str) -> List[int]:
        text = text.strip()
        if not text:
            return []
        parts = [p.strip() for p in text.split(".") if p.strip()]
        nums = [int(x) for x in parts]
        if any(n <= 0 for n in nums):
            raise ValueError("clues must be positive integers")
        return nums

    def _parse_clues(self) -> bool:
        try:
            for line in self.row_clues:
                for n in line:
                    if not isinstance(n, int) or n <= 0:
                        raise ValueError("clues must be positive integers")
            for line in self.col_clues:
                for n in line:
                    if not isinstance(n, int) or n <= 0:
                        raise ValueError("clues must be positive integers")
            return True
        except Exception as exc:
            messagebox.showerror("Input Error", str(exc))
            return False

    def new_puzzle(self) -> None:
        result = _SizeDialog(self, self.width, self.height).result
        if result is None:
            return
        self.width, self.height = result
        self.row_clues = [[] for _ in range(self.height)]
        self.col_clues = [[] for _ in range(self.width)]
        self.grid = [[UNKNOWN for _ in range(self.width)] for _ in range(self.height)]
        self._update_hint_sizes()
        self._redraw_hints()
        self._redraw_grid()
        self.grid_canvas.tkraise()
        self.lift()
        self.focus_force()
        self.log("New puzzle created")

    def open_puzzle(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            puzzle = Puzzle.load_json(path)
            self.width = puzzle.width
            self.height = puzzle.height
            self.row_clues = puzzle.row_clues
            self.col_clues = puzzle.col_clues
            self.grid = puzzle.grid
            self._update_hint_sizes()
            self._redraw_hints()
            self._redraw_grid()
            self.log(f"Loaded {path}")
        except Exception as exc:
            messagebox.showerror("Open Error", str(exc))

    def save_puzzle(self) -> None:
        if not self._parse_clues():
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            puzzle = Puzzle(
                width=self.width,
                height=self.height,
                row_clues=self.row_clues,
                col_clues=self.col_clues,
                grid=self.grid,
            )
            puzzle.save_json(path)
            self.log(f"Saved {path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def reset_grid(self) -> None:
        for r in range(self.height):
            for c in range(self.width):
                self._set_cell(r, c, UNKNOWN)
        self.log("Grid reset")

    def solve_puzzle(self) -> None:
        if self.solve_thread and self.solve_thread.is_alive():
            messagebox.showinfo("Solve", "Solver already running")
            return
        if not self._parse_clues():
            return

        self.stop_event.clear()
        self.log("Solving...")

        def run() -> None:
            start = time.time()

            def progress_cb(stage, stats):
                self.queue.put(("progress", stage, stats))

            result = solve_nonogram(
                [row[:] for row in self.grid],
                self.row_clues,
                self.col_clues,
                stop_event=self.stop_event,
                progress_cb=progress_cb,
            )
            elapsed = time.time() - start
            self.queue.put(("done", result, elapsed))

        self.solve_thread = threading.Thread(target=run, daemon=True)
        self.solve_thread.start()

    def stop_solve(self) -> None:
        if self.solve_thread and self.solve_thread.is_alive():
            self.stop_event.set()
            self.log("Stop requested")

    def step_puzzle(self) -> None:
        if not self._parse_clues():
            return
        ok, changed = propagate_once(self.grid, self.row_clues, self.col_clues)
        if not ok:
            self.log("Contradiction in step")
            messagebox.showerror("Step", "Contradiction detected")
            return
        if changed == 0:
            self.log("No changes in step")
        else:
            self.log(f"Step applied, changed {changed} cells")
            for r in range(self.height):
                for c in range(self.width):
                    self.grid_canvas.itemconfig(
                        self.cell_items[r][c],
                        fill=self._color_for(self.grid[r][c]),
                    )

    def _process_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                if item[0] == "progress":
                    stage, stats = item[1], item[2]
                    self.log(f"{stage}: iter={stats.iterations} fixed={stats.fixed_cells} nodes={stats.nodes}")
                elif item[0] == "done":
                    result, elapsed = item[1], item[2]
                    if result.status == "cancelled":
                        self.log("Solve cancelled")
                    elif result.status == "unsolved":
                        self.log(f"No solution in {elapsed:.2f}s")
                        messagebox.showinfo("Solve", "No solution found")
                    elif result.status == "multiple":
                        self._apply_solution(result.solutions[0])
                        self.log(f"Multiple solutions in {elapsed:.2f}s (showing first)")
                        messagebox.showinfo("Solve", "Multiple solutions found (showing first)")
                    else:
                        self._apply_solution(result.solutions[0])
                        self.log(f"Solved in {elapsed:.2f}s")
                        messagebox.showinfo("Solve", "Solved (unique)")
        except queue.Empty:
            pass
        self.after(100, self._process_queue)

    def _apply_solution(self, solution: List[List[int]]) -> None:
        self.grid = [row[:] for row in solution]
        for r in range(self.height):
            for c in range(self.width):
                self.grid_canvas.itemconfig(
                    self.cell_items[r][c],
                    fill=self._color_for(self.grid[r][c]),
                )

    def log(self, msg: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_edit_row_hint(self, event) -> None:
        y = self.row_hint_canvas.canvasy(event.y)
        r = int(y // self.cell_size)
        if not (0 <= r < self.height):
            return
        current = ".".join(str(n) for n in self.row_clues[r])
        text = simpledialog.askstring("Row Clue", f"Row {r + 1} clues:", initialvalue=current)
        if text is None:
            return
        try:
            self.row_clues[r] = self._parse_clue_text(text)
            self._redraw_hints()
        except Exception as exc:
            messagebox.showerror("Input Error", str(exc))

    def _on_edit_col_hint(self, event) -> None:
        x = self.col_hint_canvas.canvasx(event.x)
        c = int(x // self.cell_size)
        if not (0 <= c < self.width):
            return
        current = ".".join(str(n) for n in self.col_clues[c])
        text = simpledialog.askstring("Column Clue", f"Column {c + 1} clues:", initialvalue=current)
        if text is None:
            return
        try:
            self.col_clues[c] = self._parse_clue_text(text)
            self._redraw_hints()
        except Exception as exc:
            messagebox.showerror("Input Error", str(exc))


class _SizeDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Tk, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self.result: Optional[Tuple[int, int]] = None
        super().__init__(parent, title="New Puzzle")

    def body(self, master: tk.Widget) -> tk.Widget:
        ttk.Label(master, text="Width (5-25):").grid(row=0, column=0, sticky="w")
        ttk.Label(master, text="Height (5-25):").grid(row=1, column=0, sticky="w")
        self.width_var = tk.StringVar(value=str(self._width))
        self.height_var = tk.StringVar(value=str(self._height))
        self.width_entry = ttk.Entry(master, textvariable=self.width_var, width=8)
        self.height_entry = ttk.Entry(master, textvariable=self.height_var, width=8)
        self.width_entry.grid(row=0, column=1, padx=6, pady=4, sticky="w")
        self.height_entry.grid(row=1, column=1, padx=6, pady=4, sticky="w")
        return self.width_entry

    def validate(self) -> bool:
        try:
            width = int(self.width_var.get().strip())
            height = int(self.height_var.get().strip())
            if not (5 <= width <= 40 and 5 <= height <= 40):
                raise ValueError("width/height out of range")
            self.result = (width, height)
            return True
        except Exception:
            messagebox.showerror("Input Error", "Width/Height must be integers between 5 and 40.")
            return False
