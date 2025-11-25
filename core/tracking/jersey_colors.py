import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any, List
from core.config import KMEANS_MERGE_DELTA_AB

@dataclass
class ROIParams:
    #Tigher box
    y_top: float = 0.14
    y_bottom: float = 0.54
    x_left: float = 0.34
    x_right: float = 0.72

@dataclass
class KMeansParams:
    max_k: int = 5
    attempts: int = 3
    max_iter: int = 30
    eps: float = 0.4

    # odrzucanie i łączenie klastrów
    min_cluster_ratio: float = 0.03   # minimalny rozmiar klastra
    merge_delta_ab: float = 6.0       # połącz centroidy jeśli, odległość euklidesowa mniejsza niż ...

    # Minimalna liczba próbek dla kolejnych k w k-means
    min_samples_for_k4: int = 450
    min_samples_for_k5: int = 900

@dataclass
class ExtractorConfig:
    roi: ROIParams = field(default_factory=ROIParams)
    kmeans: KMeansParams = field(default_factory=KMeansParams)

    reject_grass_by_ab: bool = False
    grass_a_thr: int = 10
    grass_b_thr: int = 15

class JerseyColorExtractor:
    def __init__(self, config: Optional[ExtractorConfig] = None):
        if config is None:
            cfg = ExtractorConfig()
            cfg.kmeans.merge_delta_ab = float(KMEANS_MERGE_DELTA_AB)
            self.cfg = cfg
        else:
            self.cfg = config

    @staticmethod
    def _clip_box(x1, y1, x2, y2, w, h):
        x1 = int(max(0, min(x1, w-1))); x2 = int(max(0, min(x2, w-1)))
        y1 = int(max(0, min(y1, h-1))); y2 = int(max(0, min(y2, h-1)))
        if x2 <= x1: x2 = min(w-1, x1+1)
        if y2 <= y1: y2 = min(h-1, y1+1)
        return x1, y1, x2, y2

    def crop_roi_from_box(self, frame_bgr: np.ndarray, xyxy: Tuple[float, float, float, float]) -> Dict[str, Any]:
        H, W = frame_bgr.shape[:2]
        x1, y1, x2, y2 = map(int, xyxy)
        x1, y1, x2, y2 = self._clip_box(x1, y1, x2, y2, W, H)
        crop = frame_bgr[y1:y2, x1:x2]
        ch, cw = crop.shape[:2]

        yA = int(self.cfg.roi.y_top * ch)
        yB = int(self.cfg.roi.y_bottom * ch)
        xA = int(self.cfg.roi.x_left * cw)
        xB = int(self.cfg.roi.x_right * cw)

        yB = max(yA + 1, min(ch, yB))
        xB = max(xA + 1, min(cw, xB))

        roi = crop[yA:yB, xA:xB]

        return {
            "crop": crop, "roi": roi,
            "crop_rect": (x1, y1, x2, y2),
            "roi_rect_in_crop": (xA, yA, xB, yB)
        }

    @staticmethod
    def _merge_and_filter_clusters(centers: np.ndarray,
                                   counts: np.ndarray,
                                   total: int,
                                   delta_ab: float,
                                   min_ratio: float) -> Tuple[np.ndarray, np.ndarray]:

        keep = (counts.astype(np.float32) / float(total)) >= float(min_ratio)
        centers = centers[keep]
        counts = counts[keep]

        if centers.shape[0] == 0:
            centers = centers[:1]
            counts = np.array([total], dtype=int)
            return centers.astype(np.float32), counts.astype(int)

        used = np.zeros(len(centers), dtype=bool)
        merged_centers = []
        merged_counts = []
        for i in range(len(centers)):
            if used[i]: continue
            ci = centers[i]
            group = [i]
            used[i] = True
            for j in range(i+1, len(centers)):
                if used[j]: continue
                if np.linalg.norm(centers[j] - ci) <= delta_ab:
                    used[j] = True
                    group.append(j)
            w = counts[group].astype(np.float32)
            c = (centers[group] * w[:, None]).sum(axis=0) / max(1.0, w.sum())
            merged_centers.append(c)
            merged_counts.append(int(w.sum()))


        order = np.argsort(-np.array(merged_counts))
        centers_new = np.array(merged_centers, dtype=np.float32)[order]
        counts_new = np.array(merged_counts, dtype=int)[order]
        return centers_new, counts_new

    def kmeans_ab(self, roi_bgr: np.ndarray, k_override: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        ab_all = lab[..., 1:3].reshape(-1, 2).astype(np.float32)
        H, W = roi_bgr.shape[:2]
        px = int(H * W)

        out: Dict[str, Any] = {"lab": lab}

        if ab_all.shape[0] < 50:
            out.update({"centers_ab": None, "counts": None, "label_map": None, "keep_mask": None,
                        "roi_pixels": px, "chosen_K": None})
            return out

        if k_override is not None:
            kmin, kmax = k_override
            K = int(max(1, min(kmax, kmin)))  # jeśli (2,2) -> 2
        else:
            K = 3
            if px >= self.cfg.kmeans.min_samples_for_k5 and self.cfg.kmeans.max_k >= 5:
                K = 5
            elif px >= self.cfg.kmeans.min_samples_for_k4 and self.cfg.kmeans.max_k >= 4:
                K = 4
            K = min(K, self.cfg.kmeans.max_k)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                    self.cfg.kmeans.max_iter, self.cfg.kmeans.eps)

        _, labels, centers = cv2.kmeans(ab_all, K, None, criteria, self.cfg.kmeans.attempts, cv2.KMEANS_PP_CENTERS)
        labels = labels.ravel()
        counts = np.bincount(labels, minlength=K)
        order = np.argsort(-counts)
        centers = centers[order].astype(np.float32)
        counts = counts[order].astype(int)

        total = int(counts.sum())

        c2, n2 = self._merge_and_filter_clusters(
            centers, counts, total,
            delta_ab=self.cfg.kmeans.merge_delta_ab,
            min_ratio=self.cfg.kmeans.min_cluster_ratio
        )

        if c2.shape[0] > 0:
            diffs = ab_all[:, None, :] - c2[None, :, :]
            d2 = np.sum(diffs * diffs, axis=2)
            new_labels = np.argmin(d2, axis=1).astype(np.uint8)
            label_map = new_labels.reshape(H, W)
            new_counts = np.bincount(new_labels, minlength=c2.shape[0]).astype(int)

            ord2 = np.argsort(-new_counts)
            c2 = c2[ord2]
            new_counts = new_counts[ord2]
            remap = np.zeros_like(ord2)
            remap[ord2] = np.arange(len(ord2))
            label_map = remap[label_map]
        else:
            c2, new_counts = centers, counts
            label_map = labels.reshape(H, W).astype(np.uint8)

        keep_mask = np.ones((H, W), dtype=bool)

        out.update({
            "centers_ab": c2.astype(np.float32),
            "counts": new_counts.astype(int),
            "label_map": label_map,
            "keep_mask": keep_mask,
            "roi_pixels": px,
            "chosen_K": int(K)
        })
        return out

    def _reject_grass_centers(self, centers: np.ndarray, counts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if centers is None or len(centers) == 0: return centers, counts
        a_thr, b_thr = self.cfg.grass_a_thr, self.cfg.grass_b_thr

        keep = ~((centers[:, 0] < a_thr) & (centers[:, 1] > b_thr))
        if not np.any(keep):
            return centers, counts
        return centers[keep], counts[keep]

    def analyze_box(self, frame_bgr: np.ndarray, xyxy: Tuple[float, float, float, float]) -> Dict[str, Any]:
        c = self.crop_roi_from_box(frame_bgr, xyxy)
        km = self.kmeans_ab(c["roi"])

        centers = km.get("centers_ab")
        cnts = km.get("counts")
        if self.cfg.reject_grass_by_ab and centers is not None and cnts is not None:
            centers, cnts = self._reject_grass_centers(centers, cnts)
            if centers is not None and cnts is not None and len(centers) > 0:
                order = np.argsort(-cnts)
                km["centers_ab"] = centers[order].astype(np.float32)
                km["counts"] = cnts[order].astype(int)

        swatches_bgr: Optional[List[Tuple[int,int,int]]] = None
        if km["centers_ab"] is not None and km["centers_ab"].size:
            L_all = km["lab"][..., 0]
            L_global = float(np.median(L_all)) if L_all.size else 65.0
            swatches_bgr = []
            for a, b in km["centers_ab"]:
                lab_px = np.array([[[L_global, a, b]]], dtype=np.uint8)
                bgr = cv2.cvtColor(lab_px, cv2.COLOR_Lab2BGR)[0, 0, :]
                swatches_bgr.append(tuple(int(v) for v in bgr))

        return {**c, **km, "swatches_bgr": swatches_bgr}

    def extract_mixture_for_emd(self,
                                analysis: Dict[str, Any],
                                reject_grass: bool = True,
                                top_m: Optional[int] = None,
                                cap_each: Optional[float] = 0.18,
                                reweight_gamma: Optional[float] = None
                                ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Buduje mieszankę kolorów dla EMD.

        zwraca centra w przestrzeni 3D [L, a, b],
        gdzie L to MEDIANA jasności z całego ROI (jedna L na całą koszulkę, by ograniczyć wpłw miejscowych cieni).
        """
        centers = analysis.get("centers_ab")
        counts = analysis.get("counts")
        if centers is None or counts is None or len(centers) == 0:
            return np.empty((0, 3), np.float32), np.empty((0,), np.float32)

        centers = centers.astype(np.float32)
        weights = counts.astype(np.float32)

        wsum = float(weights.sum())
        if wsum <= 0:
            return np.empty((0, 3), np.float32), np.empty((0,), np.float32)
        weights /= wsum

        # --- usuwanie trawy po ab ---
        if reject_grass:
            a_thr, b_thr = self.cfg.grass_a_thr, self.cfg.grass_b_thr
            keep = ~((centers[:, 0] < a_thr) & (centers[:, 1] > b_thr))
            if np.any(keep):
                centers = centers[keep]
                weights = weights[keep]
                if centers.size == 0:
                    return np.empty((0, 3), np.float32), np.empty((0,), np.float32)

        # --- top M klastrów ---
        if top_m is not None and len(weights) > top_m:
            order = np.argsort(-weights)[:top_m]
            centers = centers[order]
            weights = weights[order]

        # --- limit udziału jednego klastra ---
        if cap_each is not None:
            weights = np.minimum(weights, float(cap_each))

        if reweight_gamma is not None and reweight_gamma > 0:
            weights = np.power(weights, float(reweight_gamma))

        s = float(weights.sum())
        if s > 0:
            weights /= s
        else:
            weights = np.ones_like(weights, dtype=np.float32) / float(len(weights))

        # --- budowa 3D [L, a, b] ---
        lab_img = analysis.get("lab", None)
        if lab_img is not None and getattr(lab_img, "size", 0) > 0:
            L_all = lab_img[..., 0].astype(np.float32)
            L_global = float(np.median(L_all))
        else:
            # fallback
            L_global = 170.0

        L_vec = np.full((centers.shape[0], 1), L_global, dtype=np.float32)
        centers_lab = np.concatenate([L_vec, centers.astype(np.float32)], axis=1)

        return centers_lab, weights

    def draw_debug_panel(self, frame_bgr: np.ndarray, xyxy: Tuple[int,int,int,int], analysis: Dict[str,Any]) -> np.ndarray:
        x1, y1, x2, y2 = map(int, xyxy)
        out = frame_bgr.copy()
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)

        (cx1, cy1, cx2, cy2) = analysis["crop_rect"]
        rx1, ry1, rx2, ry2 = analysis["roi_rect_in_crop"]
        rfx1, rfy1 = cx1 + rx1, cy1 + ry1
        rfx2, rfy2 = cx1 + rx2, cy1 + ry2
        cv2.rectangle(out, (rfx1, rfy1), (rfx2, rfy2), (255, 0, 0), 2)

        swatches = analysis.get("swatches_bgr")
        counts = analysis.get("counts")
        if swatches and counts is not None and len(swatches) == len(counts):
            total = int(np.sum(counts)) if np.sum(counts) > 0 else 1
            px = x2 + 6
            py = y1
            max_h = max(16, (y2 - y1))
            heights = [max(8, int(max_h * (c / total))) for c in counts]
            for (b, g, r), h in zip(swatches, heights):
                cv2.rectangle(out, (px, py), (px + 22, py + h), (int(b), int(g), int(r)), -1)
                py += h + 4
        return out

    def segmentation_rgb(self, roi_bgr, label_map, centers_ab, lab_img):
        seg_rgb = np.zeros_like(roi_bgr)
        if centers_ab is None or label_map is None or len(centers_ab) == 0:
            return seg_rgb
        L_global = float(np.median(lab_img[..., 0])) if lab_img.size else 65.0
        for k, (a, b) in enumerate(centers_ab):
            lab_center = np.array([[[L_global, a, b]]], dtype=np.uint8)
            bgr = cv2.cvtColor(lab_center, cv2.COLOR_Lab2BGR)[0, 0, :]
            seg_rgb[label_map == k] = bgr
        return seg_rgb

    def save_mask_debug(self, analysis: Dict[str, Any], save_path: str):
        roi = analysis["roi"]
        seg_rgb = self.segmentation_rgb(
            roi_bgr=roi,
            label_map=analysis.get("label_map"),
            centers_ab=analysis.get("centers_ab"),
            lab_img=analysis.get("lab"),
        )
        def to_rgb(x): return cv2.cvtColor(x, cv2.COLOR_BGR2RGB)
        tiles = [to_rgb(roi), to_rgb(seg_rgb)]
        blank = np.zeros_like(roi)
        tiles = [tiles[0], tiles[1], to_rgb(roi), to_rgb(blank)]
        col1 = np.vstack([tiles[0], tiles[2]])
        col2 = np.vstack([tiles[1], tiles[3]])
        grid = np.hstack([col1, col2])
        grid_bgr = cv2.cvtColor(grid, cv2.COLOR_RGB2BGR)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, grid_bgr)

    def analyze_roi_direct(self, roi_bgr: np.ndarray, k_override: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        km = self.kmeans_ab(roi_bgr, k_override=k_override)

        swatches_bgr = None
        if km["centers_ab"] is not None and km["centers_ab"].size:
            L_all = km["lab"][..., 0]
            L_global = float(np.median(L_all)) if L_all.size else 65.0
            swatches_bgr = []
            for a, b in km["centers_ab"]:
                lab_px = np.array([[[L_global, a, b]]], dtype=np.uint8)
                bgr = cv2.cvtColor(lab_px, cv2.COLOR_Lab2BGR)[0, 0, :]
                swatches_bgr.append(tuple(int(v) for v in bgr))

        return {"roi": roi_bgr, **km, "swatches_bgr": swatches_bgr}

# --- możliwosć szybkiego sprawdzenia dla pojedyńczego boxa:
# python jersey_colors.py --image path.jpg --box 700 180 770 360
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--box", type=int, nargs=4)
    args = parser.parse_args()
    img = cv2.imread(args.image); assert img is not None
    if not args.box:
        H, W = img.shape[:2]; bw, bh = W//6, H//3
        x1, y1 = W//2 - bw//2, H//2 - bh//2
        xyxy = (x1, y1, x1 + bw, y1 + bh)
    else:
        xyxy = tuple(args.box)
    ext = JerseyColorExtractor()
    info = ext.analyze_box(img, xyxy)
    dbg = ext.draw_debug_panel(img, xyxy, info)
    cv2.imshow("debug", dbg); cv2.waitKey(0); cv2.destroyAllWindows()
