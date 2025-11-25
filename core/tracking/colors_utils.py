import cv2
import numpy as np
from core.config import EMD_L_WEIGHT

def centroid_ab_to_bgr(a_or_center, b=None, L: int = 170):
    """
    Konwersja współrzędnych Lab na kolor BGR.

    Obsługuje dwa tryby:
    - centroid_ab_to_bgr(a, b, L=170)          -> stary interfejs (2D ab + L)
    - centroid_ab_to_bgr(center, L=170)        -> center = [L,a,b] lub [a,b]
    """
    # tryb: centroid_ab_to_bgr(center, ...)
    if b is None and not isinstance(a_or_center, (int, float, np.floating)):
        center = np.asarray(a_or_center, dtype=float).ravel()
        if center.size >= 3:
            L_val, a_val, b_val = center[0], center[1], center[2]
        elif center.size == 2:
            a_val, b_val = center[0], center[1]
            L_val = float(L)
        else:
            # coś dziwnego -> biały
            return (255, 255, 255)
    else:
        # tryb: centroid_ab_to_bgr(a, b, L=170)
        a_val = float(a_or_center)
        b_val = float(b)
        L_val = float(L)

    lab_px = np.array([[[L_val, a_val, b_val]]], dtype=np.uint8)
    bgr = cv2.cvtColor(lab_px, cv2.COLOR_Lab2BGR)[0, 0, :]
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


def team_color_from_proto(proto: dict, fallback=(255, 255, 255)):
    """
    Kolor drużyny na podstawie prototypu (centra + wagi).

    Działa zarówno, gdy centra mają kształt:
      - (N, 2)  -> [a,b]
      - (N, 3)  -> [L,a,b]
    """
    if not proto:
        return fallback
    c = proto.get("centers_ab")
    w = proto.get("weights")
    if c is None or w is None or len(w) == 0:
        return fallback

    c = np.asarray(c, dtype=np.float32)
    w = np.asarray(w, dtype=np.float32)
    if c.ndim != 2 or c.shape[0] == 0:
        return fallback

    k = int(np.argmax(w))
    center = c[k]
    return centroid_ab_to_bgr(center)


def emd_lite(centers1, weights1, centers2, weights2, unmatched_cost: float = 30.0) -> float:
    """
    Prosta, ręcznie zaimplementowana wersja Earth Mover's Distance dla:
    - centrów w przestrzeni 2D lub 3D (ab albo Lab),

    Jeśli wektor ma wymiar 3 (L,a,b), to L jest ważony mocniej
    (to poprawia separację czerni i bieli).
    """
    c1 = centers1.astype(np.float32).copy()
    w1 = weights1.astype(np.float32).copy()
    c2 = centers2.astype(np.float32).copy()
    w2 = weights2.astype(np.float32).copy()

    s1 = float(w1.sum())
    s2 = float(w2.sum())

    if s1 <= 0 and s2 <= 0:
        return 0.0
    if s1 <= 0:
        return float(w2.sum()) * unmatched_cost
    if s2 <= 0:
        return float(w1.sum()) * unmatched_cost

    w1 /= s1
    w2 /= s2

    cost = 0.0

    # --- waga jasności L* (na razie stała, potem można przenieść do configu) ---
    if c1.shape[1] == 3 and c2.shape[1] == 3:
        # [L, a, b] -> wzmacniamy L
        L_WEIGHT = float(EMD_L_WEIGHT)
        weights_dim = np.array([L_WEIGHT, 1.0, 1.0], dtype=np.float32)

        def dist_matrix(a, b): #z jasnością
            diff = (a[:, None, :] - b[None, :, :]) * weights_dim
            return np.sqrt((diff ** 2).sum(axis=2))
    else:
        def dist_matrix(a, b): #bez jasności
            diff = a[:, None, :] - b[None, :, :]
            return np.sqrt((diff ** 2).sum(axis=2))

    while len(w1) > 0 and len(w2) > 0:
        d = dist_matrix(c1, c2)

        i, j = np.unravel_index(np.argmin(d), d.shape)

        move = min(w1[i], w2[j])
        cost += move * float(d[i, j])

        w1[i] -= move
        w2[j] -= move

        if w1[i] <= 1e-8:
            c1 = np.delete(c1, i, 0)
            w1 = np.delete(w1, i)
        if w2[j] <= 1e-8:
            c2 = np.delete(c2, j, 0)
            w2 = np.delete(w2, j)

    if len(w1) > 0:
        cost += float(w1.sum()) * unmatched_cost
    if len(w2) > 0:
        cost += float(w2.sum()) * unmatched_cost

    return float(cost)
