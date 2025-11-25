import numpy as np
import supervision as sv
import cv2
import os
import csv
from typing import Dict, List, Optional, Sequence

TRI_BASE = 21
TRI_HEIGHT = 16
LABEL_ALPHA = 0.25
LABEL_MARGIN = 8

def _draw_triangle_top(frame, xyxy, color_bgr, base=TRI_BASE, height=TRI_HEIGHT, margin=LABEL_MARGIN):
    x1, y1, x2, y2 = map(int, xyxy)
    cx = (x1 + x2) // 2
    y_top = max(0, y1 - margin)
    pts = np.array([
        [cx, y_top + height],
        [cx - base // 2, y_top],
        [cx + base // 2, y_top],
    ], dtype=np.int32)
    cv2.fillPoly(frame, [pts], color_bgr)
    return frame


def _draw_label_top(frame, xyxy, text, text_color_bgr, alpha=LABEL_ALPHA, y_offset_px=0):
    x1, y1, x2, y2 = map(int, xyxy)
    overlay = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs, th = 0.6, 2
    (tw, th_px), _ = cv2.getTextSize(text, font, fs, th)

    pad_x, pad_y = 6, 4
    box_w = max(tw + 2 * pad_x, min(220, (x2 - x1)))
    box_h = th_px + 2 * pad_y

    top_anchor = max(0, y1 - y_offset_px - LABEL_MARGIN)
    by2 = max(0, top_anchor)
    by1 = max(0, by2 - box_h)
    bx1 = x1
    bx2 = x1 + box_w

    #Background
    cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (0, 0, 0), -1)
    frame[:] = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    #Text
    tx = bx1 + pad_x
    ty = by2 - pad_y
    cv2.putText(frame, text, (tx, ty), font, fs, text_color_bgr, th, cv2.LINE_AA)
    return frame

def annotate_people_custom_labels(frame, detections: sv.Detections,
                                       id_to_name: dict, label_texts: list,
                                       label_colors_bgr: list,
                                       triangle_colors_bgr: list = None):

    if len(detections) == 0:
        return frame

    class_ids = detections.class_id.astype(int)
    names = np.array([id_to_name[int(cid)].lower() for cid in class_ids])
    mask_people = np.isin(names, ["player", "referee", "goalkeeper"])

    if triangle_colors_bgr is None:
        triangle_colors_bgr = label_colors_bgr

    for i in range(len(detections)):
        if not mask_people[i]:
            continue
        tri_color = triangle_colors_bgr[i] if triangle_colors_bgr[i] is not None else (255, 255, 255)
        xyxy = detections.xyxy[i]
        frame = _draw_triangle_top(frame, xyxy, tri_color, base=TRI_BASE, height=TRI_HEIGHT, margin=LABEL_MARGIN)

    y_offset = TRI_HEIGHT
    for i in range(len(detections)):
        if not mask_people[i]:
            continue
        text = label_texts[i]
        if text is None:
            continue
        color_bgr = label_colors_bgr[i] if label_colors_bgr[i] is not None else (255, 255, 255)
        xyxy = detections.xyxy[i]
        frame = _draw_label_top(frame, xyxy, text, color_bgr, alpha=LABEL_ALPHA, y_offset_px=y_offset)

    return frame


# Loggery
class AnnotationLogger:
    """
    Loguje to, co jest rysowane na klatce:
    - bbox (x1,y1,x2,y2)
    - nazwa klasy (player/goalkeeper/referee/...)
    - tracker_id
    - tekst labela
    - kolor labela
    - kolor trójkąta
    - confidence detekcji
    """
    def __init__(self, out_dir: str, fps: float):
        os.makedirs(out_dir, exist_ok=True)
        self.csv_path = os.path.join(out_dir, "annotations_stream.csv")
        self._f = open(self.csv_path, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow([
            "frame",
            "time_s",
            "det_idx",
            "tracker_id",
            "class_name",
            "label_text",
            "label_b",
            "label_g",
            "label_r",
            "tri_b",
            "tri_g",
            "tri_r",
            "conf",
            "x1",
            "y1",
            "x2",
            "y2",
        ])
        self._fps = float(fps) if fps else 25.0

    def close(self):
        try:
            self._f.flush()
            self._f.close()
        except Exception:
            pass

    def log_frame(
        self,
        frame_idx: int,
        detections,
        names,
        tracker_ids,
        label_texts: Sequence[Optional[str]],
        label_colors_bgr: Sequence[Optional[tuple]],
        triangle_colors_bgr: Sequence[Optional[tuple]],
    ):
        if detections is None or len(detections) == 0:
            return

        t_s = frame_idx / self._fps
        confs = getattr(detections, "confidence", None)

        for i in range(len(detections)):
            class_name = str(names[i]).lower().strip()

            if class_name == "ball":
                continue

            try:
                tid = int(tracker_ids[i]) if tracker_ids is not None else -1
            except Exception:
                tid = -1

            text = ""
            if i < len(label_texts) and label_texts[i] is not None:
                text = str(label_texts[i])

            lb = label_colors_bgr[i] if i < len(label_colors_bgr) else None
            tr = triangle_colors_bgr[i] if i < len(triangle_colors_bgr) else None

            def _col_or_empty(col, idx):
                if col is None:
                    return ""
                try:
                    return int(col[idx])
                except Exception:
                    return ""

            lb_b = _col_or_empty(lb, 0)
            lb_g = _col_or_empty(lb, 1)
            lb_r = _col_or_empty(lb, 2)

            tr_b = _col_or_empty(tr, 0)
            tr_g = _col_or_empty(tr, 1)
            tr_r = _col_or_empty(tr, 2)

            if confs is not None and i < len(confs):
                try:
                    conf_val = float(confs[i])
                except Exception:
                    conf_val = ""
            else:
                conf_val = ""

            x1, y1, x2, y2 = map(float, detections.xyxy[i])

            self._w.writerow([
                int(frame_idx),
                f"{t_s:.3f}",
                int(i),
                int(tid),
                class_name,
                text,
                lb_b, lb_g, lb_r,
                tr_b, tr_g, tr_r,
                conf_val,
                f"{x1:.1f}",
                f"{y1:.1f}",
                f"{x2:.1f}",
                f"{y2:.1f}",
            ])


class PitchKPLogger:
    """
    Loguje keypointy boiska,
    """
    def __init__(self, out_dir: str, fps: float):
        os.makedirs(out_dir, exist_ok=True)
        self.csv_path = os.path.join(out_dir, "pitch_keypoints_stream.csv")
        self._f = open(self.csv_path, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow([
            "frame",
            "time_s",
            "kp_id",
            "x_px",
            "y_px",
            "conf",
        ])
        self._fps = float(fps) if fps else 25.0

    def close(self):
        try:
            self._f.flush()
            self._f.close()
        except Exception:
            pass

    def log(self, frame_idx: int, pts_dict: Dict[int, tuple], conf_dict: Dict[int, float]):
        if not pts_dict:
            return
        t_s = frame_idx / self._fps
        for kp_id, (x, y) in pts_dict.items():
            c = conf_dict.get(kp_id, 0.0)
            self._w.writerow([
                int(frame_idx),
                f"{t_s:.3f}",
                int(kp_id),
                f"{float(x):.1f}",
                f"{float(y):.1f}",
                f"{float(c):.3f}",
            ])

