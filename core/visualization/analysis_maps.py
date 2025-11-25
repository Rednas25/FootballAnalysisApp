import os
import csv
from collections import defaultdict
from typing import Dict, Tuple, Iterable, List, Optional

import numpy as np
import cv2
from core.config import (
    MAP_WIDTH as CFG_MAP_WIDTH,
    MAP_HEIGHT as CFG_MAP_HEIGHT,
    HM_BINS_W as CFG_HM_BINS_W,
    HM_BINS_H as CFG_HM_BINS_H,
    HM_GAUSS_BLUR_K as CFG_HM_GAUSS_BLUR_K,
    HM_ALPHA_OVERLAY as CFG_HM_ALPHA_OVERLAY,
    HM_MIN_SAMPLES as CFG_HM_MIN_SAMPLES,
    HM_USE_QUALITY_ONLY as CFG_HM_USE_QUALITY_ONLY,
)

# Rozmiar generowanych obrazków
MAP_WIDTH, MAP_HEIGHT = CFG_MAP_WIDTH, CFG_MAP_HEIGHT

# Parametry heatmap.
HM_BINS: Tuple[int, int] = (CFG_HM_BINS_W, CFG_HM_BINS_H)      # (W,H) siatki heatmapy w układzie pitch01
GAUSS_BLUR_K: int = CFG_HM_GAUSS_BLUR_K     # rozmiar jądra Gaussa
COLORMAP = cv2.COLORMAP_JET                 # kolormap do wizualizacji
ALPHA_OVERLAY: float = CFG_HM_ALPHA_OVERLAY    # przezroczystość nakładki heatmapy na boisko
MIN_SAMPLES: int = CFG_HM_MIN_SAMPLES       # minimalna liczba próbek, by zapisać heatmapę
USE_QUALITY_ONLY: bool = CFG_HM_USE_QUALITY_ONLY    # filtr quality_ok == 1

# ----------------------------------------------fs-----------------------------
# WSPÓLNE NARZĘDZIA: obraz boiska
# ---------------------------------------------------------------------------

def load_pitch_image(pitch_img_path: str, size_wh: Tuple[int, int]) -> np.ndarray:
    """
    Wczytuje obraz boiska.
    """
    if not pitch_img_path:
        raise ValueError("pitch_img_path is None.")

    if not os.path.isfile(pitch_img_path):
        raise FileNotFoundError(f"Pitch image not found: {pitch_img_path}")

    img = cv2.imread(pitch_img_path)
    if img is None:
        raise RuntimeError(f"cv2.imread failed to load pitch image: {pitch_img_path}")

    w, h = size_wh
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------------------
# HEATMAPY
# ---------------------------------------------------------------------------

def hist2d_pitch01(points: Iterable[Tuple[float, float]],
                   bins: Tuple[int, int] = HM_BINS) -> np.ndarray:
    """
    Buduje histogram 2D (H,W) dla punktów w [0..1]x[0..1].
    Zwraca macierz int32, gdzie:
        H = bins[1], W = bins[0]
    """
    W, H = bins
    hm = np.zeros((H, W), dtype=np.int32)
    pts = list(points)
    if not pts:
        return hm

    arr = np.array(pts, dtype=np.float32)
    xs = np.clip(arr[:, 0], 0.0, 0.9999) * W
    ys = np.clip(arr[:, 1], 0.0, 0.9999) * H
    xs = xs.astype(np.int32)
    ys = ys.astype(np.int32)
    for x, y in zip(xs, ys):
        hm[y, x] += 1
    return hm


def heatmap_to_color(hm: np.ndarray, blur_k: int = GAUSS_BLUR_K,
                     colormap=COLORMAP) -> np.ndarray:
    """
    Normalizuje histogram do [0..255], rozmycie Gaussa o wartości z config.ini
    i nakłada wybrany colormap.
    """
    if hm.size == 0:
        return np.zeros((MAP_HEIGHT, MAP_WIDTH, 3), dtype=np.uint8)

    hmax = float(hm.max())
    if hmax <= 0:
        norm = np.zeros_like(hm, dtype=np.uint8)
    else:
        norm = (hm.astype(np.float32) / hmax * 255.0).astype(np.uint8)

    u8 = norm
    if blur_k and blur_k > 1:
        k = int(blur_k) | 1
        u8 = cv2.GaussianBlur(u8, (k, k), 0)

    colored = cv2.applyColorMap(u8, colormap)  # BGR
    return colored


def overlay_on_pitch(colored_hm: np.ndarray, pitch_img: np.ndarray, alpha: float = ALPHA_OVERLAY) -> np.ndarray:
    """
    Skaluje heatmapę do rozmiaru boiska i wykonuje overlay.
    """
    ph, pw = pitch_img.shape[:2]
    hm_resized = cv2.resize(colored_hm, (pw, ph), interpolation=cv2.INTER_LINEAR)
    overlay = cv2.addWeighted(pitch_img, 1.0, hm_resized, float(alpha), 0.0)
    return overlay


def save_npz_png(hm: np.ndarray, base_path_noext: str, pitch_img: np.ndarray) -> None:
    """
    Zapisuje:
    - plik .npz z histogramem,
    - PNG z samą heatmapą,
    - PNG z heatmapą nałożoną na boisko.
    """
    os.makedirs(os.path.dirname(base_path_noext), exist_ok=True)
    # 1) surowy histogram
    np.savez_compressed(base_path_noext + ".npz",
                        heatmap=hm,
                        bins=np.array(HM_BINS, np.int32))
    # 2) heatmapa
    colored = heatmap_to_color(hm, blur_k=GAUSS_BLUR_K, colormap=COLORMAP)
    colored_resized = cv2.resize(colored, (MAP_WIDTH, MAP_HEIGHT), interpolation=cv2.INTER_LINEAR)
    cv2.imwrite(base_path_noext + ".png", colored_resized)
    # 3) overlay na boisko
    ov = overlay_on_pitch(colored, pitch_img, alpha=ALPHA_OVERLAY)
    cv2.imwrite(base_path_noext + "_overlay.png", ov)

# ---------------------------------------------------------------------------
# AVERAGE POSITIONS
# ---------------------------------------------------------------------------

def load_positions(csv_path: str,
                   use_quality_only: bool = True,
                   frame_min: Optional[int] = None,
                   frame_max: Optional[int] = None,
                   allowed_teams: Optional[Iterable[str]] = None
                   ) -> Dict[Tuple[str, int], List[Tuple[float, float]]]:
    """
    Wczytuje positions_stream.csv i zwraca słownik:
        data[(team, number)] = lista (x01, y01)

    Role (GK/player) są ignorowane – średnia jest liczona po numerze zawodnika.
    Opcjonalne filtry:
    - frame_min, frame_max: zakres numerów klatek (włącznie),
    - allowed_teams: lista nazw drużyn, np. ["TEAM A", "TEAM B"].
    """
    data: Dict[Tuple[str, int], List[Tuple[float, float]]] = defaultdict(list)
    allowed_set = set(t.strip().upper() for t in allowed_teams) if allowed_teams else None

    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        has_quality = "quality_ok" in (r.fieldnames or [])

        for row in r:
            # filtr po jakości
            if use_quality_only and has_quality:
                try:
                    if int(row["quality_ok"]) != 1:
                        continue
                except Exception:
                    pass

            # filtr po numerze klatki
            frame_idx: Optional[int] = None
            try:
                if "frame" in row and row["frame"]:
                    frame_idx = int(row["frame"])
                elif "frame_idx" in row and row["frame_idx"]:
                    frame_idx = int(row["frame_idx"])
            except Exception:
                frame_idx = None

            if frame_min is not None and frame_idx is not None and frame_idx < frame_min:
                continue
            if frame_max is not None and frame_idx is not None and frame_idx > frame_max:
                continue

            try:
                team = row["team"].strip()
                # filtr po drużynie
                if allowed_set is not None:
                    if team is None:
                        continue
                    team_tag = team.strip().upper()
                    if team_tag not in allowed_set:
                        continue

                number = int(row["number"])
                x01 = float(row["x01"])
                y01 = float(row["y01"])
            except Exception:
                continue

            if not (0.0 <= x01 <= 1.0 and 0.0 <= y01 <= 1.0):
                continue

            data[(team, number)].append((x01, y01))

    return data


def compute_means(data: Dict[Tuple[str, int], List[Tuple[float, float]]],
                  min_samples: int = 5
                  ) -> Dict[Tuple[str, int], Tuple[float, float, int]]:
    """
    Liczy średnie pozycje (x, y) dla każdej grupy (TEAM, number).
    Zwraca:
        means[(team,number)] = (x_mean, y_mean, liczba_próbek)
    """
    means: Dict[Tuple[str, int], Tuple[float, float, int]] = {}
    for key, pts in data.items():
        if len(pts) < min_samples:
            continue
        arr = np.array(pts, dtype=np.float32)
        m = np.mean(arr, axis=0)
        if np.any(~np.isfinite(m)):
            continue
        means[key] = (float(m[0]), float(m[1]), int(len(pts)))
    return means


def draw_means_on_pitch(pitch_img: np.ndarray,
                        means: Dict[Tuple[str, int], Tuple[float, float, int]],
                        team_colors: Dict[str, Tuple[int, int, int]],
                        label_scale: float = 0.3,
                        dot_radius: int = 8,
                        gk_thickness: int = 2) -> np.ndarray:
    """
    Rysuje punkty średnich pozycji na obrazie boiska.
    Role są ignorowane – GK rozpoznajemy wyłącznie po numerze (number == 1).
    """
    out = pitch_img.copy()
    h, w = out.shape[:2]

    # GŁÓWNE PUNKTY
    for (team, number), (mx, my, n) in means.items():
        col = team_colors.get(team, (255, 255, 255))
        px = int(np.clip(mx, 0, 1) * (w - 1))
        py = int(np.clip(my, 0, 1) * (h - 1))

        cv2.circle(out, (px, py), dot_radius, col, -1, lineType=cv2.LINE_AA)

        # Bramkarz – numer 1 dostaje obwódkę
        if number == 1:
            cv2.circle(
                out,
                (px, py),
                dot_radius + 3,
                (255, 255, 255),
                gk_thickness,
                lineType=cv2.LINE_AA,
            )

        # numer zawodnika w środku kropki
        label = str(number)
        (tw, th), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, label_scale, 1
        )
        tx = int(px - tw / 2)
        ty = int(py + th / 2)

        # outline: czarny + biały (dla lepszej widoczności)
        cv2.putText(out, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    label_scale, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(out, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    label_scale, (255, 255, 255), 1, cv2.LINE_AA)

    # LEGENDA W PRAWYM DOLNYM ROGU
    teams_present: List[str] = []
    for (team, _) in means.keys():
        if team in team_colors and team not in teams_present:
            teams_present.append(team)

    if teams_present:
        margin_right = 44
        margin_bottom = 20
        line_spacing = 20

        base_x = w - margin_right
        base_y = h - margin_bottom

        # najpierw TEAM A, potem TEAM B
        order = [t for t in ["TEAM A", "TEAM B"] if t in teams_present]
        for t in teams_present:
            if t not in order:
                order.append(t)

        for i, team in enumerate(order):
            col = team_colors.get(team, (255, 255, 255))
            cy = base_y - i * line_spacing
            cx = base_x

            # kropka legendy
            cv2.circle(out, (cx, cy), 7, col, -1, lineType=cv2.LINE_AA)

            # tekst po lewej stronie kropki
            label = team
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            tx = cx - 10 - tw
            ty = cy + int(th / 2)

            cv2.putText(out, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)

    return out


def save_means_csv(means: Dict[Tuple[str, int], Tuple[float, float, int]],
                   out_csv: str) -> None:
    """
    Zapisuje dane średnich do CSV.
    Role są ignorowane przy liczeniu średnich – do CSV wpisujemy:
        'GK' dla numeru 1, 'player' dla pozostałych.
    """
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["team", "number", "role", "samples", "x01_mean", "y01_mean"])
        for (team, number), (mx, my, n) in sorted(means.items(),
                                                 key=lambda kv: (kv[0][0], kv[0][1])):
            role = "GK" if number == 1 else "player"
            w.writerow([team, number, role, n, f"{mx:.6f}", f"{my:.6f}"])

