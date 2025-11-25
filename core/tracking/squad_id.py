from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
import numpy as np


@dataclass
class Slot:
    number: int
    team: str
    role: str
    tid: Optional[int] = None
    last_pos: Optional[np.ndarray] = None            # (x, y) w pitch01
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2, np.float32))
    last_seen: int = -10**9
    miss_count: int = 0
    owner_tid: Optional[int] = None
    owner_seen: int = -10**9
    attach_frame: int = -10**9
    just_detached_frame: int = -10**9


class SquadIDManager:
    def __init__(self,
                 match_radius: float = 0.001,
                 ttl_frames: int = 150,
                 warmup_frames: int = 3,
                 expand_per_miss: float = 0.0005,
                 vel_alpha: float = 0.0,
                 team_switch_hold: int = 3,
                 lock_reid_until: int = 6,
                 breakaway_factor: float = 1.5,
                 owner_lock_frames: int = 0):
        self.match_radius = match_radius
        self.ttl_frames = ttl_frames
        self.warmup_frames = warmup_frames
        self.expand_per_miss = expand_per_miss
        self.vel_alpha = vel_alpha
        self.team_switch_hold = team_switch_hold
        self.lock_reid_until = lock_reid_until
        self.breakaway_factor = breakaway_factor
        self.owner_lock_frames = owner_lock_frames

        self.slots: Dict[str, Dict[int, Slot]] = {
            "TEAM A": {1: Slot(1, "TEAM A", "GK"), **{n: Slot(n, "TEAM A", "player") for n in range(2, 12)}},
            "TEAM B": {1: Slot(1, "TEAM B", "GK"), **{n: Slot(n, "TEAM B", "player") for n in range(2, 12)}},
        }

        # tid -> (team, number)
        self.mapping: Dict[int, Tuple[str, int]] = {}
        # tid -> (team, role, [pos...], first_frame_seen)
        self.pending: Dict[int, Tuple[str, str, List[np.ndarray], int]] = {}
        # licznik mismatch
        self.team_mismatch: Dict[int, int] = {}

    # ---------- funkcje pomocnicze ----------
    def _dist_to_slot(self, team: str, num: int, pos: Optional[np.ndarray]) -> float:
        s = self.slots[team][num]
        if pos is None or not np.isfinite(pos).all() or s.last_pos is None:
            return float("inf")
        pred = self._predict(s)
        return float(np.linalg.norm(pred - pos))

    def _predict(self, slot: Slot) -> np.ndarray:
        if slot.last_pos is None:
            return np.array([np.nan, np.nan], np.float32)
        return slot.last_pos + slot.velocity * max(1, slot.miss_count)

    def _update_slot_motion(self, slot: Slot, new_pos: np.ndarray):
        if slot.last_pos is None:
            slot.velocity = np.zeros(2, np.float32)
        else:
            est_vel = new_pos - slot.last_pos
            slot.velocity = (1 - self.vel_alpha) * slot.velocity + self.vel_alpha * est_vel
        slot.last_pos = new_pos

    def _best_free_number_for_pos(self, team: str, role: str, pos: Optional[np.ndarray]) -> Optional[int]:
        if pos is None or not np.isfinite(pos).all():
            return None
        best_n, best_d = None, float("inf")
        for n, s in self.slots[team].items():
            if s.role != role or s.tid is not None or s.last_pos is None:
                continue
            pred = self._predict(s)
            d = float(np.linalg.norm(pred - pos))
            if d < best_d:
                best_d, best_n = d, n
        return best_n

    def _best_match_slot(self, team: str, role: str, pos: np.ndarray, candidate_tid: int, frame_idx: int) -> Optional[int]:
        best_n, best_d = None, float("inf")
        for n, s in self.slots[team].items():
            if s.role != role or s.last_pos is None:
                continue
            if s.tid is not None:
                continue

            allow_now = (frame_idx - s.just_detached_frame) <= 2

            if not allow_now:
                if s.miss_count < self.lock_reid_until:
                    continue
                if s.owner_tid is not None and s.owner_tid != candidate_tid:
                    if (frame_idx - s.owner_seen) <= self.owner_lock_frames:
                        continue

            pred = self._predict(s)
            d = float(np.linalg.norm(pred - pos))
            rad = self.match_radius + self.expand_per_miss * s.miss_count
            if allow_now:
                rad *= 0.9
            if d <= rad and d < best_d:
                best_d, best_n = d, n
        return best_n

    def _first_free_number(self, team: str, role: str) -> Optional[int]:
        pool = [1] if role == "GK" else list(range(2, 12))
        for n in pool:
            if self.slots[team][n].tid is None:
                return n
        return None

    def _assign(self, tid: int, team: str, role: str, pos: np.ndarray, frame_idx: int):
        n = self._best_match_slot(team, role, pos, candidate_tid=tid, frame_idx=frame_idx)
        if n is None:
            n = self._best_free_number_for_pos(team, role, pos)
            if n is None:
                n = self._first_free_number(team, role)
                if n is None:
                    cands = [s for s in self.slots[team].values() if s.role == role]
                    if pos is not None and np.isfinite(pos).all():
                        cands.sort(key=lambda s: (s.last_pos is None,
                                                  float('inf') if s.last_pos is None else np.linalg.norm(self._predict(s) - pos)))
                    else:
                        cands.sort(key=lambda s: (s.tid is None, -s.miss_count, -s.last_seen))
                    n = cands[0].number

        slot = self.slots[team][n]
        slot.tid = tid
        slot.owner_tid = tid
        slot.owner_seen = frame_idx
        slot.attach_frame = frame_idx
        slot.last_seen = frame_idx
        slot.miss_count = 0
        self._update_slot_motion(slot, pos)
        self.mapping[tid] = (team, n)
        self.team_mismatch.pop(tid, None)

    # ---------- Main Update ----------
    def update(self,
               tracker_ids: List[int],
               pts_pitch01: List[Optional[np.ndarray]],
               teams: List[Optional[str]],
               roles: List[str],
               frame_idx: int) -> Dict[int, Tuple[str, int]]:
        seen_tids = set()
        tid_pos: Dict[int, Optional[np.ndarray]] = {}
        tid_role: Dict[int, str] = {}

        for tid, pos, team, role in zip(tracker_ids, pts_pitch01, teams, roles):
            tid_pos[tid] = pos
            tid_role[tid] = role

            if team not in ("TEAM A", "TEAM B"):
                if tid in self.mapping and pos is not None and np.isfinite(pos).all():
                    tm, num = self.mapping[tid]
                    s = self.slots[tm][num]
                    s.last_seen = frame_idx
                    s.miss_count = 0
                    self._update_slot_motion(s, pos)
                continue

            seen_tids.add(tid)
            if pos is None or not np.isfinite(pos).all():
                continue

            # --- Istniejące trackery ---
            if tid in self.mapping:
                tm, num = self.mapping[tid]
                s = self.slots[tm][num]
                s.last_seen = frame_idx
                s.miss_count = 0
                self._update_slot_motion(s, pos)

                # (anti-swap)
                pred = self._predict(s)
                rad = self.match_radius + self.expand_per_miss * max(1, s.miss_count)
                dist = float(np.linalg.norm(pred - pos))
                if dist > self.breakaway_factor * rad:
                    s.tid = None
                    s.miss_count = 1
                    s.owner_tid = None
                    s.owner_seen = frame_idx
                    s.just_detached_frame = frame_idx

                    self.mapping.pop(tid, None)
                    self.pending[tid] = (team, role, [pos], frame_idx)
                    self.team_mismatch.pop(tid, None)
                    return dict(self.mapping)

                # debounce (team_switch_hold) - Przytrzymanie decyzji zmiany drużyny ---
                if tm != team:
                    prev = self.team_mismatch.get(tid, 0) + 1
                    self.team_mismatch[tid] = prev
                    # print(f"[team] mismatch tid={tid} {tm}->{team} count={prev} @frame {frame_idx}")
                    if prev >= self.team_switch_hold:
                        if s.tid == tid:
                            s.tid = None
                            s.miss_count = 1
                            s.just_detached_frame = frame_idx
                            s.owner_tid = None
                            s.owner_seen = frame_idx

                        self.mapping.pop(tid, None)
                        self.pending[tid] = (team, role, [pos], frame_idx)
                        self.team_mismatch.pop(tid, None)
                        # print(f"[team] SWITCH tid={tid} {tm}->{team} @frame {frame_idx}")
                        continue
                else:
                    self.team_mismatch.pop(tid, None)

            # --- Nowy/powracający tracker ---
            else:
                if tid not in self.pending:
                    self.pending[tid] = (team, role, [pos], frame_idx)
                else:
                    tm, rl, buf, first = self.pending[tid]
                    if tm != team or rl != role:
                        self.pending[tid] = (team, role, [pos], frame_idx)
                    else:
                        buf.append(pos)
                        if len(buf) >= self.warmup_frames:
                            avg = np.mean(np.stack(buf, axis=0), axis=0).astype(np.float32)
                            self._assign(tid, team, role, avg, frame_idx)
                            self.pending.pop(tid, None)

        # --- anty-duplikaty ---
        teamnum_to_tids: Dict[Tuple[str, int], List[int]] = {}
        for tid, (tm, num) in list(self.mapping.items()):
            if tid in seen_tids and tm in ("TEAM A", "TEAM B"):
                teamnum_to_tids.setdefault((tm, num), []).append(tid)

        for (tm, num), tids_dup in teamnum_to_tids.items():
            if len(tids_dup) <= 1:
                continue
            slot = self.slots[tm][num]

            if slot.tid in tids_dup:
                winner = slot.tid
            else:
                def _stability_score(tid_):
                    owner_bonus = 1 if slot.owner_tid == tid_ else 0
                    age = 0
                    if slot.tid == tid_:
                        age = max(0, frame_idx - slot.attach_frame)
                    dist = self._dist_to_slot(tm, num, tid_pos.get(tid_))
                    return (owner_bonus, age, -dist)

                winner = max(tids_dup, key=_stability_score)

            for t in tids_dup:
                if t == winner:
                    continue
                role = tid_role.get(t, slot.role)

                pos = tid_pos.get(t)
                newn = self._best_free_number_for_pos(tm, role, pos)
                if newn is None:
                    newn = self._first_free_number(tm, role)
                    if newn is None:
                        cands = [s for s in self.slots[tm].values() if s.role == role]
                        if pos is not None and np.isfinite(pos).all():
                            cands.sort(key=lambda s: (s.last_pos is None,
                                                      float('inf') if s.last_pos is None else np.linalg.norm(self._predict(s) - pos)))
                        else:
                            cands.sort(key=lambda s: (s.tid is None, -s.miss_count, -s.last_seen))
                        newn = cands[0].number

                old_tm, old_num = self.mapping.get(t, (tm, num))
                if (old_tm, old_num) != (tm, newn):
                    old_slot = self.slots[old_tm][old_num]
                    if old_slot.tid == t:
                        old_slot.tid = None

                new_slot = self.slots[tm][newn]
                new_slot.tid = t
                new_slot.owner_tid = t
                new_slot.owner_seen = frame_idx
                new_slot.attach_frame = frame_idx
                new_slot.last_seen = frame_idx
                new_slot.miss_count = 0
                p = tid_pos.get(t)
                if p is not None and np.isfinite(p).all():
                    self._update_slot_motion(new_slot, p)
                self.mapping[t] = (tm, newn)

            self.slots[tm][num].tid = winner
            self.slots[tm][num].attach_frame = max(self.slots[tm][num].attach_frame, frame_idx)
            self.mapping[winner] = (tm, num)

        for team in ("TEAM A", "TEAM B"):
            for n, s in list(self.slots[team].items()):
                if s.tid is not None and s.tid not in seen_tids:
                    s.miss_count += 1
                    if s.miss_count > self.ttl_frames:
                        self.slots[team][n] = Slot(n, team, s.role)
                        for k, v in list(self.mapping.items()):
                            if v == (team, n):
                                self.mapping.pop(k, None)
                elif s.tid is None and s.last_pos is not None:
                    s.miss_count += 1
                    if s.miss_count > self.ttl_frames:
                        self.slots[team][n] = Slot(n, team, s.role)

        for tid, (tm, rl, buf, first) in list(self.pending.items()):
            if frame_idx - first > self.ttl_frames:
                self.pending.pop(tid, None)

        # ===== [DEBUG] miss_count dla wszystkich slotów (głównie miejsce debuggingu ReID) =====
        if frame_idx % 5 == 0:
            def _line(team: str) -> str:
                parts = []
                for n in sorted(self.slots[team].keys()):
                    s = self.slots[team][n]
                    val = s.miss_count
                    star = "*" if val > self.ttl_frames else ""
                    occ = "!" if s.tid is not None else ""
                    parts.append(f"#{n}={val}{star}{occ}")
                return " ".join(parts)
            print(f"[miss] TEAM A: {_line('TEAM A')}  |  TEAM B: {_line('TEAM B')} @frame {frame_idx}")

        return dict(self.mapping)

    # ---------- debug: reID zones ----------
    def get_reid_zones(self) -> List[dict]:
        zones = []
        for team in ("TEAM A", "TEAM B"):
            for n, s in self.slots[team].items():
                if s.tid is None and s.last_pos is not None and 0 < s.miss_count <= self.ttl_frames:
                    center = self._predict(s)
                    rad = self.match_radius + self.expand_per_miss * s.miss_count
                    zones.append({
                        "team": team,
                        "number": n,
                        "role": s.role,
                        "center01": center.astype(np.float32),
                        "radius01": float(rad),
                    })
        return zones
