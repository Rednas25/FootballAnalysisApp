from __future__ import annotations
from typing import Tuple, Optional


PENALTY_DEPTH_X = 16.5 / 105.0
PENALTY_WIDTH_Y = 40.32 / 68.0

CENTRAL_BAND_X_MIN = 0.20
CENTRAL_BAND_X_MAX = 0.80

def in_bounds01(p: Tuple[float, float]) -> bool:
    x, y = p
    return 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0

def is_in_central_band(p: Tuple[float, float],
                       x_min: float = CENTRAL_BAND_X_MIN,
                       x_max: float = CENTRAL_BAND_X_MAX) -> bool:
    if p is None: return False
    x, _ = p
    return (x_min <= x <= x_max)

def is_in_left_penalty(p: Tuple[float, float]) -> bool:
    if p is None: return False
    x, y = p
    y_mid = 0.5
    half = PENALTY_WIDTH_Y / 2.0
    return (0.0 <= x <= PENALTY_DEPTH_X) and (y_mid - half <= y <= y_mid + half)

def is_in_right_penalty(p: Tuple[float, float]) -> bool:
    if p is None: return False
    x, y = p
    y_mid = 0.5
    half = PENALTY_WIDTH_Y / 2.0
    return (1.0 - PENALTY_DEPTH_X <= x <= 1.0) and (y_mid - half <= y <= y_mid + half)

def penalty_side(p: Tuple[float, float]) -> Optional[str]:
    if is_in_left_penalty(p):  return "LEFT"
    if is_in_right_penalty(p): return "RIGHT"
    return None

def is_near_touchline(p01, margin_x: float = 0.12) -> bool:
    if p01 is None:
        return False
    x = float(p01[0])
    return (x <= margin_x) or (x >= 1.0 - margin_x)
