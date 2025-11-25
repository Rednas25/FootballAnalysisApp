import os, csv
import numpy as np
from typing import Dict, Tuple, Optional, Iterable

class PositionsLogger:
    """
    Streamingowy zapis pozycji zawodników do CSV z lekkim gate'em jakości.
    - loguje od zadanej klatki (start_frame, domyślnie 5)
    - wymaga: homografia gotowa, stabilne przypisanie TEAM:#, brak pending switch, brak dużego skoku
    - każda próbka ma flagę quality_ok (0/1) i powód ewentualnego odrzucenia (reason)
    """
    def __init__(self,
                 out_dir: str,
                 fps: float,
                 minimap_size: Tuple[int, int] = (600, 350),
                 start_frame: int = 5,
                 min_stable_frames: int = 5,
                 max_delta01: float = 0.08):
        os.makedirs(out_dir, exist_ok=True)
        self.csv_path = os.path.join(out_dir, "positions_stream.csv")
        self._csv = open(self.csv_path, "w", newline="", encoding="utf-8")
        self._wr = csv.writer(self._csv)
        self._wr.writerow([
            "frame","time_s","team","number","role","x01","y01","x_px","y_px",
            "quality_ok","stable_age","delta01","reason"
        ])

        self._fps = float(fps or 25.0)
        self._mm_w, self._mm_h = minimap_size

        # stan jakości
        self._stable_key: Dict[int, Tuple[str,int]] = {}   # tid -> (TEAM, num)
        self._stable_age: Dict[int, int] = {}              # ile klatek ten sam (TEAM, num)
        self._last_p01: Dict[Tuple[str,int], np.ndarray] = {}  # (TEAM,num) -> (x,y)

        self.start_frame = int(start_frame)
        self.min_stable_frames = int(min_stable_frames)
        self.max_delta01 = float(max_delta01)

    def close(self):
        try:
            self._csv.flush()
            self._csv.close()
        except Exception:
            pass

    def _write_row(self, frame_idx: int, team: str, num: int, role: str,
                   p01_xy: Tuple[float,float], quality_ok: bool,
                   stable_age: int, delta01: float, reason: str):
        if p01_xy is None or not np.isfinite(p01_xy).all():
            return
        x01 = float(np.clip(p01_xy[0], 0.0, 1.0))
        y01 = float(np.clip(p01_xy[1], 0.0, 1.0))
        x_px = int(x01 * (self._mm_w - 1))
        y_px = int(y01 * (self._mm_h - 1))
        t_s = frame_idx / self._fps
        self._wr.writerow([
            int(frame_idx), f"{t_s:.3f}", team, int(num), role,
            f"{x01:.6f}", f"{y01:.6f}", x_px, y_px,
            int(1 if quality_ok else 0), int(stable_age), f"{delta01:.5f}", reason
        ])

    def log_from_detections(self,
                            frame_idx: int,
                            detections,                # sv.Detections (xyxy, class_id, tracker_id)
                            names: np.ndarray,         # np.array of class names (lowercase)
                            tracker_ids: Iterable[int],
                            tid_to_teamnum: Dict[int, Tuple[str,int]],
                            homography,               # HomographyEstimator
                            stabilizer,               # Stabilizer
                            referee_ids: Optional[Iterable[int]] = None):
        """
        Wywołuj po policzeniu tid_to_teamnum (czyli po SquadIDManager.update()).
        """
        if frame_idx < self.start_frame:
            return
        if homography is None or not homography.is_ready():
            return  # brak wiarygodnych współrzędnych pitch2D

        ref_ids = set(referee_ids or [])

        for i in range(len(detections)):
            cname = names[i]
            if cname not in ("player", "goalkeeper"):
                continue

            # pomiń obiekty będące (z dużym prawdopodobieństwem) sędziami
            try:
                tid_i = int(tracker_ids[i])
            except Exception:
                continue
            if tid_i in ref_ids:
                continue

            # wymagamy stabilnego numeru TEAM:# (od SquadIDManager)
            if tid_i not in tid_to_teamnum:
                continue
            team_tag, num = tid_to_teamnum[tid_i]
            role = "GK" if cname == "goalkeeper" else "player"

            # pozycja: użycie dołu  bboxa
            x1, y1, x2, y2 = map(float, detections.xyxy[i])
            foot = np.array([[0.5 * (x1 + x2), y2]], dtype=np.float32)
            p01 = homography.image_to_pitch01(foot)
            if p01 is None or not np.isfinite(p01).all():
                continue
            p01_xy = (float(p01[0, 0]), float(p01[0, 1]))
            if not (0.0 <= p01_xy[0] <= 1.0 and 0.0 <= p01_xy[1] <= 1.0):
                continue

            # gate: pending switch w Stabilizerze -> pomiń
            st_i = stabilizer.get(tid_i)
            pending = (st_i.pending_team is not None)

            # gate: stabilne przypisanie (tid -> (TEAM,num)) przez N klatek
            prev_key = self._stable_key.get(tid_i)
            cur_key = (team_tag, num)
            if prev_key != cur_key:
                self._stable_key[tid_i] = cur_key
                self._stable_age[tid_i] = 0
            else:
                self._stable_age[tid_i] = self._stable_age.get(tid_i, 0) + 1
            stable_age = self._stable_age.get(tid_i, 0)

            # gate: anty-skok (delta pozycji względem ostatniej próbki dla TEAM:num)
            last_xy = self._last_p01.get(cur_key)
            if last_xy is not None and np.isfinite(last_xy).all():
                delta01 = float(np.hypot(p01_xy[0] - last_xy[0], p01_xy[1] - last_xy[1]))
            else:
                delta01 = 0.0
            self._last_p01[cur_key] = np.array(p01_xy, np.float32)

            quality_ok = (not pending) and (stable_age >= self.min_stable_frames) and (delta01 <= self.max_delta01)
            reason = ""
            if pending: reason = "pending_switch"
            elif stable_age < self.min_stable_frames: reason = "warming"
            elif delta01 > self.max_delta01: reason = "jump"

            self._write_row(frame_idx, team_tag, num, role, p01_xy,
                            quality_ok, stable_age, delta01, reason)
