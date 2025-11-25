from ultralytics import YOLO
import time

try:
    import torch
except Exception:  # torch nie dostępny dla każdego pythona
    torch = None


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


class YoloRunner:
    def __init__(
        self,
        model_path,
        device: str | None = "auto",
        imgsz: int = 1280,
        conf: float = 0.4,
    ):
        self.device = _auto_select_device(device)
        self.model = YOLO(model_path)
        if self.device == "cuda":
            try:
                self.model.to("cuda")
                print("[YOLO] Model moved to CUDA")
            except Exception as e:
                print("[YOLO] Could not move model to CUDA:", e)

        self.imgsz = imgsz
        self.conf = conf
        self._perf_frames = 0
        self._perf_time = 0.0

        print(f"[YOLO] Loaded model '{model_path}' on device: {self.device}")

    @property
    def class_names(self):
        # dict: {id: name}
        return getattr(self.model, "model", self.model).names

    def predict_video_stream(self, source):
        """
        Strumieniowa predykcja YOLO z prostym pomiarem czasu na klatkę.
        """
        start = time.perf_counter()
        for result in self.model.predict(
            source=source,
            device=self.device,
            imgsz=self.imgsz,
            conf=self.conf,
            agnostic_nms=True,
            iou=0.58,
            max_det=100,
            save=False,
            stream=True,
            verbose=False,
            half=(self.device == "cuda"),  # FP16 dla GPU dla poprawy wydajności
        ):
            end = time.perf_counter()
            # ~czas przetwarzania 1 klatki przez YOLO
            self._perf_frames += 1
            self._perf_time += (end - start)

            yield result
            start = time.perf_counter()

    def print_perf_summary(self):
        """Wypisuje czas YOLO na 1 klatkę + FPS."""
        if self._perf_frames <= 0 or self._perf_time <= 0.0:
            print("[YOLO PERF] Brak danych (nie wykonano predykcji).")
            return

        avg_ms = (self._perf_time / self._perf_frames) * 1000.0
        fps = 1000.0 / avg_ms
        print("[YOLO PERF] Frames:", self._perf_frames)
        print(f"[YOLO PERF] {avg_ms:.2f} ms/klatka  (~{fps:.1f} FPS tylko YOLO)")
