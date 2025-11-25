import cv2
import csv
import os
import numpy as np

from .annotation import (
    _draw_triangle_top,
    TRI_BASE,
    TRI_HEIGHT,
    LABEL_ALPHA,
    LABEL_MARGIN,
)


# ==============================
#   USTAWIENIA WEJŚCIOWE
# ==============================

VIDEO_PATH = r"C:\Users\kacpe\PycharmProjects\fussball2\assets\videos\czelsiliv(normalcolors).mp4"
FRAMES_DIR = r"C:\Users\kacpe\PycharmProjects\fussball2\assets\frames"
START_FRAME = 1

# Jeśli chcesz maksymalny możliwy FPS – ustaw na False (delay 1 ms)
LOCK_TO_VIDEO_FPS = True  # False = zawsze delay 1 ms


# ==============================
#   FUNKCJE POMOCNICZE
# ==============================

def _parse_color_from_row(row, prefix: str):
    b_key = f"{prefix}_b"
    g_key = f"{prefix}_g"
    r_key = f"{prefix}_r"
    try:
        b = row.get(b_key, "")
        g = row.get(g_key, "")
        r = row.get(r_key, "")
    except AttributeError:
        return None
    if b == "" or g == "" or r == "":
        return None
    try:
        return (int(float(b)), int(float(g)), int(float(r)))
    except Exception:
        return None


def load_annotations(csv_path: str):
    """
    Ładujemy CSV raz, od razu parsując:
    - bbox -> tuple intów
    - tekst
    - kolory (label/triangle)
    Dzięki temu w pętli nie ma już konwersji string->float/int.
    """
    ann_by_frame = {}
    if not os.path.isfile(csv_path):
        print(f"[WARN] annotations CSV not found: {csv_path}")
        return ann_by_frame

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cnt_rows = 0
        for row in reader:
            try:
                frame = int(row["frame"])
            except Exception:
                continue

            try:
                x1 = float(row["x1"])
                y1 = float(row["y1"])
                x2 = float(row["x2"])
                y2 = float(row["y2"])
            except Exception:
                continue

            bbox = (
                int(round(x1)),
                int(round(y1)),
                int(round(x2)),
                int(round(y2)),
            )

            text = row.get("label_text", "") or ""

            label_color = _parse_color_from_row(row, "label")
            tri_color = _parse_color_from_row(row, "tri")

            ann = {
                "bbox": bbox,
                "text": text,
                "label_color": label_color,
                "tri_color": tri_color,
            }

            ann_by_frame.setdefault(frame, []).append(ann)
            cnt_rows += 1

    print(f"[INFO] loaded {cnt_rows} annotation rows for {len(ann_by_frame)} frames from {csv_path}")
    return ann_by_frame


def load_pitch_kp(csv_path: str):
    """
    Tak samo jak wyżej – od razu zapisujemy gotowe intowe (x, y).
    """
    kp_by_frame = {}
    if not os.path.isfile(csv_path):
        print(f"[WARN] pitch keypoints CSV not found: {csv_path}")
        return kp_by_frame

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cnt_rows = 0
        for row in reader:
            try:
                frame = int(row["frame"])
                x = float(row["x_px"])
                y = float(row["y_px"])
            except Exception:
                continue

            px = int(round(x))
            py = int(round(y))

            kp_by_frame.setdefault(frame, []).append((px, py))
            cnt_rows += 1

    print(f"[INFO] loaded {cnt_rows} pitch keypoints rows for {len(kp_by_frame)} frames from {csv_path}")
    return kp_by_frame


def draw_overlays(
    frame,
    annotations_for_frame,
    pitch_kp_for_frame,
    show_labels: bool = True,
    show_triangles: bool = True,
    show_kp: bool = True,
):
    h, w = frame.shape[:2]

    # ===== 1) TRÓJKĄTY NAD GŁOWĄ (tak jak w pipeline) =====
    if show_triangles:
        for ann in annotations_for_frame or []:
            x1, y1, x2, y2 = ann["bbox"]
            tri_color = ann["tri_color"] or (255, 255, 255)

            x1c = max(0, min(w - 1, x1))
            x2c = max(0, min(w - 1, x2))
            y1c = max(0, min(h - 1, y1))
            y2c = max(0, min(h - 1, y2))

            xyxy = (x1c, y1c, x2c, y2c)

            frame = _draw_triangle_top(
                frame,
                xyxy,
                tri_color,
                base=TRI_BASE,
                height=TRI_HEIGHT,
                margin=LABEL_MARGIN,
            )

    # ===== 2) LABEL NAD TRÓJKĄTEM – BATCH OVERLAY =====
    if show_labels:
        overlay = frame.copy()
        text_items = []

        font = cv2.FONT_HERSHEY_SIMPLEX
        fs, thickness = 0.6, 2
        pad_x, pad_y = 6, 4

        for ann in annotations_for_frame or []:
            text = ann["text"]
            if not text:
                continue

            x1, y1, x2, y2 = ann["bbox"]
            label_color = ann["label_color"] or (255, 255, 255)

            x1c = max(0, min(w - 1, x1))
            x2c = max(0, min(w - 1, x2))
            y1c = max(0, min(h - 1, y1))
            y2c = max(0, min(h - 1, y2))

            (tw, th_px), _ = cv2.getTextSize(text, font, fs, thickness)

            box_w = max(tw + 2 * pad_x, min(220, (x2c - x1c)))
            box_h = th_px + 2 * pad_y

            top_anchor = max(0, y1c - TRI_HEIGHT - LABEL_MARGIN)
            by2 = max(0, top_anchor)
            by1 = max(0, by2 - box_h)
            bx1 = x1c
            bx2 = min(w - 1, x1c + box_w)

            # tło labela na overlay (czarny prostokąt)
            cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (0, 0, 0), -1)

            tx = bx1 + pad_x
            ty = by2 - pad_y
            text_items.append((text, (tx, ty), label_color))

        # jeden alpha-blend dla wszystkich labeli naraz
        frame[:] = cv2.addWeighted(overlay, LABEL_ALPHA, frame, 1 - LABEL_ALPHA, 0.0)

        # teraz tekst na finalnym obrazie
        for text, (tx, ty), label_color in text_items:
            cv2.putText(
                frame,
                text,
                (tx, ty),
                font,
                fs,
                label_color,
                thickness,
                cv2.LINE_AA,
            )

    # ===== 3) KEYPOINTY BOISKA =====
    if show_kp:
        for (px, py) in pitch_kp_for_frame or []:
            if 0 <= px < w and 0 <= py < h:
                cv2.circle(frame, (px, py), 3, (0, 255, 255), -1, lineType=cv2.LINE_AA)

    return frame


# ==============================
#   GŁÓWNA FUNKCJA REPLAY
# ==============================

def main():
    ann_path = os.path.join(FRAMES_DIR, "annotations_stream.csv")
    kp_path = os.path.join(FRAMES_DIR, "pitch_keypoints_stream.csv")

    annotations = load_annotations(ann_path)
    kp = load_pitch_kp(kp_path)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"[ERROR] cannot open video: {VIDEO_PATH}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25.0
    delay_ms = max(1, int(1000 / fps)) if LOCK_TO_VIDEO_FPS else 1

    show_labels = True
    show_triangles = True
    show_kp = True

    frame_idx = 0

    win_name = "Replay Overlays (b:labels, n:triangles, m:keypoints, SPACE:pause, q:quit)"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1280, 720)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        if frame_idx < START_FRAME:
            continue

        anns = annotations.get(frame_idx, [])
        kpf = kp.get(frame_idx, [])

        frame = draw_overlays(
            frame,
            anns,
            kpf,
            show_labels=show_labels,
            show_triangles=show_triangles,
            show_kp=show_kp,
        )

        hud = (
            f"frame {frame_idx} | "
            f"B-labels: {'ON' if show_labels else 'OFF'} | "
            f"N-triangles: {'ON' if show_triangles else 'OFF'} | "
            f"M-kp: {'ON' if show_kp else 'OFF'}"
        )
        cv2.putText(
            frame,
            hud,
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.imshow(win_name, frame)
        key = cv2.waitKey(delay_ms) & 0xFF

        if key in (ord("q"), 27):  # q / ESC
            break

        elif key == ord(" "):  # pauza
            while True:
                key2 = cv2.waitKey(0) & 0xFF
                if key2 in (ord("q"), 27):
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                if key2 == ord(" "):
                    break
                if key2 == ord("b"):
                    show_labels = not show_labels
                    print(f"[TOGGLE] labels -> {show_labels}")
                elif key2 == ord("n"):
                    show_triangles = not show_triangles
                    print(f"[TOGGLE] triangles -> {show_triangles}")
                elif key2 == ord("m"):
                    show_kp = not show_kp
                    print(f"[TOGGLE] keypoints -> {show_kp}")

        elif key == ord("b"):
            show_labels = not show_labels
            print(f"[TOGGLE] labels -> {show_labels}")
        elif key == ord("n"):
            show_triangles = not show_triangles
            print(f"[TOGGLE] triangles -> {show_triangles}")
        elif key == ord("m"):
            show_kp = not show_kp
            print(f"[TOGGLE] keypoints -> {show_kp}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
