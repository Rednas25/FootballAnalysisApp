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
        # wybór urządzenia
        self.device = _auto_select_device(device)

        # załadowanie modelu
        self.model = YOLO(model_path)

        # przerzucamy model na GPU (ale zostawiamy FP32 – half robimy w predict)
        if self.device == "cuda":
            try:
                self.model.to("cuda")
                print("[YOLO] Model moved to CUDA (FP32)")
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
        HALF precision włączamy przez parametr `half=` tylko na GPU.
        """
        start = time.perf_counter()

        for result in self.model.predict(
            source=source,
            device=self.device,
            imgsz=self.imgsz,
            conf=self.conf,
            agnostic_nms=True,
            iou=0.58,
            max_det=300,
            save=False,
            stream=True,
            verbose=False,
            half=(self.device == "cuda"),  # <-- FP16 tylko na GPU
        ):
            end = time.perf_counter()
            # czas od poprzedniego yielda do tego = ~czas przetwarzania 1 klatki przez YOLO
            self._perf_frames += 1
            self._perf_time += (end - start)

            yield result

            # przygotuj start do pomiaru następnej iteracji
            start = time.perf_counter()

    def print_perf_summary(self):
        """Wypisuje ⌀ czas YOLO na 1 klatkę + FPS."""
        if self._perf_frames <= 0 or self._perf_time <= 0.0:
            print("[YOLO PERF] Brak danych (nie wykonano predykcji).")
            return

        avg_ms = (self._perf_time / self._perf_frames) * 1000.0
        fps = 1000.0 / avg_ms
        print("[YOLO PERF] Frames:", self._perf_frames)
        print(f"[YOLO PERF] ⌀ {avg_ms:.2f} ms/klatka  (~{fps:.1f} FPS tylko YOLO)")
