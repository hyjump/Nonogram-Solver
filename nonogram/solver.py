from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Optional, Tuple

UNKNOWN = -1
EMPTY = 0
FILLED = 1


class Cancelled(Exception):
    pass


@dataclass
class SolveStats:
    iterations: int = 0
    nodes: int = 0
    max_depth: int = 0
    fixed_cells: int = 0


@dataclass
class SolveResult:
    status: str
    solutions: List[List[List[int]]]
    stats: SolveStats
    message: str


def _check_cancel(stop_event) -> None:
    if stop_event is not None and stop_event.is_set():
        raise Cancelled()


@lru_cache(maxsize=20000)
def _line_candidates(
    length: int, blocks: Tuple[int, ...], line_state: Tuple[int, ...]
) -> Tuple[Tuple[int, ...], ...]:
    # Generate all line patterns that match blocks and current line_state.
    if not blocks:
        for v in line_state:
            if v == FILLED:
                return tuple()
        return (tuple(EMPTY for _ in range(length)),)

    candidates: List[Tuple[int, ...]] = []
    line = [EMPTY] * length

    def place(idx: int, pos: int) -> None:
        if idx == len(blocks):
            for i in range(pos, length):
                if line_state[i] == FILLED:
                    return
            candidates.append(tuple(line))
            return

        block = blocks[idx]
        remaining = blocks[idx + 1 :]
        min_rem_len = sum(remaining) + max(0, len(remaining))
        max_start = length - (block + min_rem_len)

        for start in range(pos, max_start + 1):
            ok = True
            for i in range(pos, start):
                if line_state[i] == FILLED:
                    ok = False
                    break
            if not ok:
                continue
            for i in range(start, start + block):
                if line_state[i] == EMPTY:
                    ok = False
                    break
            if not ok:
                continue

            for i in range(start, start + block):
                line[i] = FILLED

            next_pos = start + block
            if idx < len(blocks) - 1:
                if next_pos >= length:
                    for i in range(start, start + block):
                        line[i] = EMPTY
                    continue
                if line_state[next_pos] == FILLED:
                    ok = False
                else:
                    line[next_pos] = EMPTY
                if ok:
                    place(idx + 1, next_pos + 1)
                line[next_pos] = EMPTY
            else:
                place(idx + 1, next_pos)

            for i in range(start, start + block):
                line[i] = EMPTY

    place(0, 0)
    return tuple(candidates)


def _intersect_candidates(candidates: Tuple[Tuple[int, ...], ...]) -> List[int]:
    if not candidates:
        return []
    length = len(candidates[0])
    result = [UNKNOWN] * length
    for i in range(length):
        v = candidates[0][i]
        same = True
        for cand in candidates[1:]:
            if cand[i] != v:
                same = False
                break
        result[i] = v if same else UNKNOWN
    return result


def _is_solved(grid: List[List[int]]) -> bool:
    for row in grid:
        for v in row:
            if v == UNKNOWN:
                return False
    return True


def _count_fixed(grid: List[List[int]]) -> int:
    return sum(1 for row in grid for v in row if v != UNKNOWN)


def propagate(
    grid: List[List[int]],
    row_clues: List[List[int]],
    col_clues: List[List[int]],
    stop_event=None,
    progress_cb: Optional[Callable[[str, SolveStats], None]] = None,
) -> Tuple[bool, SolveStats]:
    height = len(grid)
    width = len(grid[0])
    stats = SolveStats()

    changed = True
    while changed:
        _check_cancel(stop_event)
        changed = False
        stats.iterations += 1

        for r in range(height):
            line_state = tuple(grid[r])
            blocks = tuple(row_clues[r])
            candidates = _line_candidates(width, blocks, line_state)
            if not candidates:
                return False, stats
            intersection = _intersect_candidates(candidates)
            for c in range(width):
                if intersection[c] != UNKNOWN and grid[r][c] != intersection[c]:
                    grid[r][c] = intersection[c]
                    changed = True

        for c in range(width):
            line_state = tuple(grid[r][c] for r in range(height))
            blocks = tuple(col_clues[c])
            candidates = _line_candidates(height, blocks, line_state)
            if not candidates:
                return False, stats
            intersection = _intersect_candidates(candidates)
            for r in range(height):
                if intersection[r] != UNKNOWN and grid[r][c] != intersection[r]:
                    grid[r][c] = intersection[r]
                    changed = True

        stats.fixed_cells = _count_fixed(grid)
        if progress_cb:
            progress_cb("propagate", stats)

    return True, stats


def propagate_once(
    grid: List[List[int]],
    row_clues: List[List[int]],
    col_clues: List[List[int]],
) -> Tuple[bool, int]:
    height = len(grid)
    width = len(grid[0])
    changed_count = 0

    for r in range(height):
        line_state = tuple(grid[r])
        blocks = tuple(row_clues[r])
        candidates = _line_candidates(width, blocks, line_state)
        if not candidates:
            return False, changed_count
        intersection = _intersect_candidates(candidates)
        for c in range(width):
            if intersection[c] != UNKNOWN and grid[r][c] != intersection[c]:
                grid[r][c] = intersection[c]
                changed_count += 1

    for c in range(width):
        line_state = tuple(grid[r][c] for r in range(height))
        blocks = tuple(col_clues[c])
        candidates = _line_candidates(height, blocks, line_state)
        if not candidates:
            return False, changed_count
        intersection = _intersect_candidates(candidates)
        for r in range(height):
            if intersection[r] != UNKNOWN and grid[r][c] != intersection[r]:
                grid[r][c] = intersection[r]
                changed_count += 1

    return True, changed_count


def _best_branch_line(
    grid: List[List[int]],
    row_clues: List[List[int]],
    col_clues: List[List[int]],
) -> Tuple[str, int, Tuple[Tuple[int, ...], ...]]:
    height = len(grid)
    width = len(grid[0])
    best_type = ""
    best_index = -1
    best_candidates: Tuple[Tuple[int, ...], ...] = tuple()
    best_count = 10**9

    for r in range(height):
        if UNKNOWN not in grid[r]:
            continue
        line_state = tuple(grid[r])
        candidates = _line_candidates(width, tuple(row_clues[r]), line_state)
        count = len(candidates)
        if count > 1 and count < best_count:
            best_count = count
            best_type = "row"
            best_index = r
            best_candidates = candidates

    for c in range(width):
        line_state = tuple(grid[r][c] for r in range(height))
        if UNKNOWN not in line_state:
            continue
        candidates = _line_candidates(height, tuple(col_clues[c]), line_state)
        count = len(candidates)
        if count > 1 and count < best_count:
            best_count = count
            best_type = "col"
            best_index = c
            best_candidates = candidates

    return best_type, best_index, best_candidates


def solve_nonogram(
    grid: List[List[int]],
    row_clues: List[List[int]],
    col_clues: List[List[int]],
    stop_event=None,
    progress_cb: Optional[Callable[[str, SolveStats], None]] = None,
    max_solutions: int = 2,
) -> SolveResult:
    width = len(grid[0])
    solutions: List[List[List[int]]] = []
    stats = SolveStats()

    def dfs(cur_grid: List[List[int]], depth: int) -> None:
        _check_cancel(stop_event)
        stats.nodes += 1
        stats.max_depth = max(stats.max_depth, depth)

        ok, pstats = propagate(cur_grid, row_clues, col_clues, stop_event, progress_cb)
        stats.iterations += pstats.iterations
        stats.fixed_cells = _count_fixed(cur_grid)
        if not ok:
            return

        if _is_solved(cur_grid):
            solutions.append([row[:] for row in cur_grid])
            return

        line_type, index, candidates = _best_branch_line(cur_grid, row_clues, col_clues)
        if not candidates:
            return

        for cand in candidates:
            if len(solutions) >= max_solutions:
                return
            new_grid = [row[:] for row in cur_grid]
            if line_type == "row":
                for c in range(width):
                    new_grid[index][c] = cand[c]
            else:
                for r in range(len(new_grid)):
                    new_grid[r][index] = cand[r]
            dfs(new_grid, depth + 1)

    try:
        start_grid = [row[:] for row in grid]
        dfs(start_grid, 0)
    except Cancelled:
        return SolveResult(
            status="cancelled",
            solutions=[],
            stats=stats,
            message="Solve cancelled",
        )

    if not solutions:
        return SolveResult(
            status="unsolved",
            solutions=[],
            stats=stats,
            message="No solution",
        )

    if len(solutions) >= 2:
        return SolveResult(
            status="multiple",
            solutions=solutions[:2],
            stats=stats,
            message="Multiple solutions found",
        )

    return SolveResult(
        status="solved",
        solutions=solutions,
        stats=stats,
        message="Unique solution",
    )
