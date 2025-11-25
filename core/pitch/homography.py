import numpy as np
import cv2

class HomographyEstimator:
    def __init__(self, template_pts_xy_norm: np.ndarray, ema=0.9):
        self.template = template_pts_xy_norm.astype(np.float32)  # [0..1]
        self.H = None
        self.ema = float(ema)
        self._ok_frames = 0

    def _reproj_err(self, H, img_pts: np.ndarray, tmpl_pts: np.ndarray) -> float:
        """Średni błąd w przestrzeni [0..1]."""
        p = cv2.perspectiveTransform(img_pts.reshape(-1,1,2).astype(np.float32), H).reshape(-1,2)
        return float(np.mean(np.linalg.norm(p - tmpl_pts, axis=1)))

    def update(self, image_pts_dict: dict[int, tuple[float, float]]):
        """
        image_pts_dict: {id: (x_px, y_px)} – piksele z obrazu kamery
        template (self.template): (N,2) w [0..1] – punkty szablonu boiska
        """
        ids = sorted(set(range(len(self.template))).intersection(image_pts_dict.keys()))
        if len(ids) < 4:
            return self.H

        img  = np.array([image_pts_dict[i] for i in ids], dtype=np.float32)  # px
        tmpl = self.template[ids].astype(np.float32)                          # [0..1]

        # 1) RANSAC w [0..1] → threshold musi być około 1% szerokości
        H_ransac, inlier_mask = cv2.findHomography(img, tmpl, cv2.RANSAC, ransacReprojThreshold=0.01)
        if H_ransac is None:
            return self.H

        # 2) Refinement: zwykłe LS na samych inlierach
        inl = inlier_mask.ravel().astype(bool) if inlier_mask is not None else None
        if inl is not None and inl.sum() >= 4:
            H_refine, _ = cv2.findHomography(img[inl], tmpl[inl], 0)
            H_new = H_refine if H_refine is not None else H_ransac
        else:
            H_new = H_ransac

        # sanity-check: błąd reprojekcji w [0..1] nie większy niż 1.5%
        err = self._reproj_err(H_new, img, tmpl)
        if not np.isfinite(err) or err > 0.015:
            return self.H

        # 3) EMA dla płynności(Wartość konfigurowalna w config.ini)
        if self.H is None:
            self.H = H_new
        else:
            self.H = (self.ema * self.H) + ((1.0 - self.ema) * H_new)

        self._ok_frames += 1
        return self.H

    def is_ready(self, min_frames=2):
        return self.H is not None and self._ok_frames >= min_frames

    def image_to_pitch01(self, pts_xy: np.ndarray) -> np.ndarray | None:
        if self.H is None:
            return None
        pts = pts_xy.reshape(-1,1,2).astype(np.float32)
        out = cv2.perspectiveTransform(pts, self.H).reshape(-1,2)
        return out
