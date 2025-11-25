import cv2
import numpy as np
from typing import Dict, Any, Tuple, Optional
from core.tracking.jersey_colors import JerseyColorExtractor

BOX_COLOR = (0, 255, 255)
BOX_THICK = 2
TEXT_BG = (0, 0, 0)
TEXT_FG = (255, 255, 255)

HELP_BROWSE = "Klatki: a=-1, d=+1, s=-30, w=+30 | f=wybierz | q=wyjdz"
HELP_DRAW   = "LPM: rysuj/pusc = zaakceptuj | r=reset | f=OK | x=pomin | q=wyjdz"

ROLE_SEQUENCE = [
    ("teamA_player",     "Wybierz Zawodnika druzyny A  (narysuj box na koszulce)"),
    ("teamB_player",     "Wybierz Zawodnika druzyny A(narysuj box na koszulce)"),
    ("teamA_goalkeeper", "Wybierz Bramkarza druzyny B (narysuj box na koszulce)"),
    ("teamB_goalkeeper", "Wybierz Bramkarza druzyny B (narysuj box na koszulce)"),
    ("referee",          "Wybierz Sedziego (narysuj box)"),
]

def _put_multiline(img, lines, org=(8, 22), scale=0.65):
    x, y = org
    for line in lines:
        cv2.putText(img, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, TEXT_BG, 3, cv2.LINE_AA)
        cv2.putText(img, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, TEXT_FG, 1, cv2.LINE_AA)
        y += int(22 * scale + 10)

def _draw_rect(img, p1, p2, color=BOX_COLOR, thick=BOX_THICK):
    x1, y1 = p1; x2, y2 = p2
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thick)

def browse_frames(video_path: str, caption: Optional[str] = None) -> Tuple[Optional[int], Optional[np.ndarray]]:
    """
    PRZEGLĄDARKA KLATEK — teraz z opcjonalnym 'caption' (np. nazwa roli),
    abyś mógł wybrać INNĄ klatkę dla każdej roli (A/B/GK/REF).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("❌ Nie można otworzyć wideo:", video_path); return None, None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS) or 25.0

    win = "Wybor_klatki"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1280, 720)

    def goto(i):
        i = max(0, min(i, total - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        return i, (f if ok else None)

    idx, frame = goto(0)
    while frame is not None:
        disp = frame.copy()
        header = [f"Klatka {idx + 1}/{total} (~{idx / fps:.2f}s) | {HELP_BROWSE}"]
        if caption:
            header.insert(0, caption)
        _put_multiline(disp, header, (10, 28), 0.7)
        cv2.imshow(win, disp)

        key = cv2.waitKey(25) & 0xFF  # ⬅️ zamiast 0 dajemy 25ms, jak w draw_box_on_image

        if key == 255:  # żadnego klawisza – odświeżaj dalej
            continue

        if key in (ord('q'), 27):
            cap.release()
            cv2.destroyWindow(win)
            return None, None
        elif key == ord('f'):
            sel = frame.copy()
            cap.release()
            cv2.destroyWindow(win)
            return idx, sel
        elif key == ord('a'):
            idx, frame = goto(idx - 1)
        elif key == ord('d'):
            idx, frame = goto(idx + 1)
        elif key == ord('s'):
            idx, frame = goto(idx - 30)
        elif key == ord('w'):
            idx, frame = goto(idx + 30)
        # inne klawisze – po prostu ignorujemy

    cap.release()
    try: cv2.destroyWindow(win)
    except: pass
    return None, None

def draw_box_on_image(frame_bgr: np.ndarray, prompt: str) -> Optional[Tuple[int,int,int,int]]:
    win = "Zaznacz ROI"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1280, 720)

    state = {"drawing": False, "p1": None, "p2": None, "final": None}

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["drawing"] = True
            state["p1"] = (x, y)
            state["p2"] = (x, y)
            state["final"] = None
        elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
            state["p2"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and state["drawing"]:
            state["drawing"] = False
            state["p2"] = (x, y)
            # finalize
            x1, y1 = state["p1"]; x2, y2 = state["p2"]
            if abs(x2 - x1) >= 4 and abs(y2 - y1) >= 4:
                x1, x2 = sorted([x1, x2]); y1, y2 = sorted([y1, y2])
                state["final"] = (x1, y1, x2, y2)

    cv2.setMouseCallback(win, on_mouse)

    while True:
        disp = frame_bgr.copy()
        _put_multiline(disp, [prompt, HELP_DRAW], (10, 28), 0.7)
        if state["drawing"] and state["p1"] and state["p2"]:
            _draw_rect(disp, state["p1"], state["p2"])
        if state["final"] is not None:
            x1, y1, x2, y2 = state["final"]
            _draw_rect(disp, (x1, y1), (x2, y2), color=(0, 200, 0), thick=2)
        cv2.imshow(win, disp)
        key = cv2.waitKey(25) & 0xFF
        if key == ord('r'):
            state = {"drawing": False, "p1": None, "p2": None, "final": None}
        elif key == ord('f'):
            cv2.destroyWindow(win)
            return state["final"]
        elif key == ord('x'):
            cv2.destroyWindow(win)
            return None
        elif key in (ord('q'), 27):
            cv2.destroyWindow(win)
            return None

def run_team_setup(
    video_path: str,
    extractor: JerseyColorExtractor,
    top_m_for_proto: int = 2) -> Dict[str, Any]:
    """
    NOWA WERSJA: dla KAŻDEJ roli najpierw wybierasz klatkę (browse_frames),
    a dopiero potem rysujesz box na wybranej klatce.
    """
    team_model: Dict[str, Any] = {}

    for key, prompt in ROLE_SEQUENCE:
        # 1) Wybór KLATKI per rola
        caption = f"[{key}] Wybierz klatke (f=zatwierdz, q=wyjście)"
        frame_idx, frame = browse_frames(video_path, caption=caption)
        if frame is None:
            print(f"⚠︎ pominięto {key} (brak wyboru klatki)")
            team_model[key] = {
                "centers_ab": np.empty((0,2), np.float32),
                "weights": np.empty((0,), np.float32),
                "box": None,
                "frame_idx": None
            }
            continue

        H, W = frame.shape[:2]

        # 2) Rysowanie ROI dla tej roli na wybranej klatce
        rect = draw_box_on_image(frame, prompt)
        if rect is None:
            team_model[key] = {
                "centers_ab": np.empty((0,2), np.float32),
                "weights": np.empty((0,), np.float32),
                "box": None,
                "frame_idx": int(frame_idx)
            }
            continue

        x1, y1, x2, y2 = rect
        x1 = max(0, min(x1, W-1)); x2 = max(0, min(x2, W-1))
        y1 = max(0, min(y1, H-1)); y2 = max(0, min(y2, H-1))
        if x2 <= x1 or y2 <= y1:
            team_model[key] = {
                "centers_ab": np.empty((0,2), np.float32),
                "weights": np.empty((0,), np.float32),
                "box": None,
                "frame_idx": int(frame_idx)
            }
            continue

        roi = frame[y1:y2, x1:x2]

        # 3) Ekstrakcja prototypów kolorów (bez zmian merytorycznych)
        analysis = extractor.analyze_roi_direct(roi_bgr=roi, k_override=(2, 2))
        centers, weights = extractor.extract_mixture_for_emd(
            analysis,
            reject_grass=False,
            top_m=top_m_for_proto,
            cap_each=None,
            reweight_gamma=None
        )

        team_model[key] = {
            "centers_ab": centers.astype(np.float32),
            "weights": weights.astype(np.float32),
            "box": (float(x1), float(y1), float(x2), float(y2)),
            "frame_idx": int(frame_idx)
        }

    return team_model

def run_single_role(
    video_path: str,
    extractor: JerseyColorExtractor,
    key: str,
    top_m_for_proto: int = 2,
):
    """
    Wersja pod GUI: obsługuje jedną rolę (teamA_player itd.)
    i oprócz prototypów zwraca też swatches_bgr (kolorki do podglądu).
    """
    prompt_map = dict(ROLE_SEQUENCE)
    prompt = prompt_map.get(key, f"Wybierz {key}")

    caption = f"[{key}] Wybierz klatke (f=Wybierz, q=Wyjdz)"
    frame_idx, frame = browse_frames(video_path, caption=caption)
    if frame is None:
        print(f"⚠︎ pominięto {key} (brak wyboru klatki)")
        return {
            "centers_ab": np.empty((0, 2), np.float32),
            "weights":    np.empty((0,), np.float32),
            "box":        None,
            "frame_idx":  None,
            "swatches_bgr": [],
        }

    H, W = frame.shape[:2]

    rect = draw_box_on_image(frame, prompt=prompt)
    if rect is None:
        print(f"⚠︎ pominięto {key} (brak boxa)")
        return {
            "centers_ab": np.empty((0, 2), np.float32),
            "weights":    np.empty((0,), np.float32),
            "box":        None,
            "frame_idx":  int(frame_idx),
            "swatches_bgr": [],
        }

    x1, y1, x2, y2 = rect
    x1 = max(0, min(x1, W - 1)); x2 = max(0, min(x2, W - 1))
    y1 = max(0, min(y1, H - 1)); y2 = max(0, min(y2, H - 1))
    if x2 <= x1 or y2 <= y1:
        print(f"⚠︎ pominięto {key} (box ma zerowy rozmiar)")
        return {
            "centers_ab": np.empty((0, 2), np.float32),
            "weights":    np.empty((0,), np.float32),
            "box":        None,
            "frame_idx":  int(frame_idx),
            "swatches_bgr": [],
        }

    roi = frame[y1:y2, x1:x2]

    # analiza ROI – tu powstają swatches_bgr (lista kolorów BGR)
    analysis = extractor.analyze_roi_direct(roi_bgr=roi, k_override=(2, 2))

    centers, weights = extractor.extract_mixture_for_emd(
        analysis,
        reject_grass=False,
        top_m=top_m_for_proto,
        cap_each=None,
        reweight_gamma=None,
    )

    swatches_bgr = analysis.get("swatches_bgr") or []

    return {
        "centers_ab": centers.astype(np.float32),
        "weights":    weights.astype(np.float32),
        "box":        (float(x1), float(y1), float(x2), float(y2)),
        "frame_idx":  int(frame_idx),
        "swatches_bgr": swatches_bgr,
    }


