from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import List

UNKNOWN = -1
EMPTY = 0
FILLED = 1


@dataclass
class Puzzle:
    width: int
    height: int
    row_clues: List[List[int]] = field(default_factory=list)
    col_clues: List[List[int]] = field(default_factory=list)
    grid: List[List[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if not self.row_clues:
            self.row_clues = [[] for _ in range(self.height)]
        if not self.col_clues:
            self.col_clues = [[] for _ in range(self.width)]
        if not self.grid:
            self.grid = [[UNKNOWN for _ in range(self.width)] for _ in range(self.height)]
        self._validate()

    def _validate(self) -> None:
        if len(self.row_clues) != self.height:
            raise ValueError("row_clues length mismatch")
        if len(self.col_clues) != self.width:
            raise ValueError("col_clues length mismatch")
        if len(self.grid) != self.height:
            raise ValueError("grid height mismatch")
        for row in self.grid:
            if len(row) != self.width:
                raise ValueError("grid width mismatch")
            for v in row:
                if v not in (UNKNOWN, EMPTY, FILLED):
                    raise ValueError("grid contains invalid value")

    @staticmethod
    def _normalize_clues(clues: List[List[int]]) -> List[List[int]]:
        result: List[List[int]] = []
        for line in clues:
            if not line:
                result.append([])
                continue
            cleaned: List[int] = []
            for n in line:
                if not isinstance(n, int) or n <= 0:
                    raise ValueError("clue values must be positive integers")
                cleaned.append(n)
            result.append(cleaned)
        return result

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "row_clues": self.row_clues,
            "col_clues": self.col_clues,
            "grid": self.grid,
        }

    def save_json(self, path: str) -> None:
        data = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_json(cls, path: str) -> "Puzzle":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        width = int(data.get("width", 0))
        height = int(data.get("height", 0))
        row_clues = cls._normalize_clues(data.get("row_clues", []))
        col_clues = cls._normalize_clues(data.get("col_clues", []))
        grid = data.get("grid", [])

        if not isinstance(grid, list) or not grid:
            grid = [[UNKNOWN for _ in range(width)] for _ in range(height)]

        return cls(
            width=width,
            height=height,
            row_clues=row_clues,
            col_clues=col_clues,
            grid=grid,
        )
