from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class TrackState:
    team: Optional[str] = None
    color: tuple = (255, 255, 255)
    last_confirm_frame: int = -10**9
    pending_team: Optional[str] = None
    pending_color: tuple = (255, 255, 255)
    pending_since_frame: Optional[int] = None

class Stabilizer:
    def __init__(self, margin_min: float, hold_frames_base: int, prox_factor: float, min_switch_frames: int = 5):
        self.margin_min = margin_min
        self.hold_frames_base = hold_frames_base
        self.prox_factor = prox_factor
        self.min_switch_frames = int(min_switch_frames)
        self.state: Dict[int, TrackState] = {}

    def get(self, obj_id: int) -> TrackState:
        if obj_id not in self.state:
            self.state[obj_id] = TrackState()
        return self.state[obj_id]
