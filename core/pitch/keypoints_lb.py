import cv2
import numpy as np
from ultralytics import YOLO

try:
    import torch
except Exception:
    torch = None

# Wybór cpu, a cuda
def _auto_select_device(device: str | None = "auto") -> str:
    if device and device != "auto":
        return str(device)

    try:
        if torch is not None:
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
    except Exception:
        pass

    return "cpu"


class PitchKeypointsDetectorLB:
    def __init__(
        self,
        weights_path: str,
        imgsz: int = 640,
        conf: float = 0.6,
        kp_conf: float = 0.8,
        device: str | None = "auto",
    ):
        self.device = _auto_select_device(device)
        self.model = YOLO(weights_path)

        # Przerzut na cuda jeśli dostępne
        if self.device == "cuda":
            try:
                self.model.to("cuda")
                print("[PitchKP] Model moved to CUDA (FP32)")
            except Exception as e:
                print("[PitchKP] Could not move model to CUDA:", e)

        self.imgsz = int(imgsz)
        self.conf = float(conf)
        self.kp_conf = float(kp_conf)

        print(f"[PitchKP] Loaded keypoints model '{weights_path}' on device: {self.device}")

    def infer_keypoints(self, frame_bgr: np.ndarray):
        H, W = frame_bgr.shape[:2]

        res = self.model.predict(
            source=frame_bgr,
            device=self.device,
            conf=self.conf,
            imgsz=self.imgsz,
            verbose=False,
            max_det=1,
            half=(self.device == "cuda"),  # <- FP16 tylko na GPU(CUDA)
        )[0]

        pts_dict, conf_dict = {}, {}
        if res.keypoints is None or res.keypoints.xy is None or len(res.keypoints.xy) == 0:
            return pts_dict, conf_dict

        xy = res.keypoints.xy
        cf = res.keypoints.conf

        xy = xy.cpu().numpy() if hasattr(xy, "cpu") else xy
        cf = cf.cpu().numpy() if hasattr(cf, "cpu") else cf

        visible_counts = (cf >= self.kp_conf).sum(axis=1)
        best_idx = int(visible_counts.argmax())

        kpts_xy = xy[best_idx].copy()
        kpts_cf = cf[best_idx].copy()

        np.clip(kpts_xy[:, 0], 0, W - 1, out=kpts_xy[:, 0])
        np.clip(kpts_xy[:, 1], 0, H - 1, out=kpts_xy[:, 1])

        for kid, (pt, c) in enumerate(zip(kpts_xy, kpts_cf)):
            if c is None or np.isnan(c) or c < self.kp_conf:
                continue
            pts_dict[kid] = (float(pt[0]), float(pt[1]))
            conf_dict[kid] = float(c)

        return pts_dict, conf_dict
