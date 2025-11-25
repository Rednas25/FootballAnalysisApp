import cv2
import numpy as np
import csv
from pathlib import Path

def load_template_norm_from_csv(pitch_png_path: str, csv_path: str) -> np.ndarray:
    """
    CSV powinno zawierać (co najmniej) kolumny: id, x, y
    x,y – piksele względem obrazu pitch.png.
    Zwraca tablicę (N,2) w [0..1] w kolejności id rosąco.
    """
    img = cv2.imread(pitch_png_path)
    assert img is not None, f"Nie mogę wczytać obrazu pitch: {pitch_png_path}"
    H, W = img.shape[:2]

    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            kid = int(row['id'])
            x = float(row['x'])
            y = float(row['y'])
            rows.append((kid, x / W, y / H))
    rows.sort(key=lambda t: t[0])
    pts = np.array([[x, y] for _, x, y in rows], dtype=np.float32)
    return pts
