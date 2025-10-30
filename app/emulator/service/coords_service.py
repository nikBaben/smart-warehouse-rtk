from typing import Tuple
from app.emulator.config import FIELD_X, FIELD_Y

ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def shelf_num_to_str(n: int) -> str:
    return ALPH[max(0, min(25, n - 1))] if n > 0 else "0"

def shelf_str_to_num(s: str | None) -> int:
    if not s:
        return 0
    s = s.strip().upper()
    if not s or s == "0":
        return 0
    c = s[0]
    return ALPH.index(c) + 1 if c in ALPH else 0

def clamp_xy(x: int, y: int) -> Tuple[int, int]:
    x = max(0, min(FIELD_X, x))
    y = max(0, min(FIELD_Y - 1, y))
    return x, y

def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
