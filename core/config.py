from dataclasses import dataclass
from pathlib import Path
from configparser import ConfigParser
import sys

def _base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()
ASSETS_DIR = BASE_DIR / "assets"
MODELS_DIR = ASSETS_DIR / "models"
PITCH_DIR = ASSETS_DIR / "pitch"

CONFIG_PATH = BASE_DIR / "config.ini"
# ---------------------------------------------------------------------------
# Wczytywanie config.ini
# ---------------------------------------------------------------------------

_cfg = ConfigParser()
if CONFIG_PATH.is_file():
    _cfg.read(CONFIG_PATH, encoding="utf-8")
else:
    print(f"[config] WARNING: {CONFIG_PATH} not found, using built-in defaults")


def _get_str(section: str, option: str, default: str) -> str:
    try:
        return _cfg.get(section, option)
    except Exception:
        return default


def _get_int(section: str, option: str, default: int) -> int:
    try:
        return _cfg.getint(section, option)
    except Exception:
        return default


def _get_float(section: str, option: str, default: float) -> float:
    try:
        return _cfg.getfloat(section, option)
    except Exception:
        return default


def _get_bool(section: str, option: str, default: bool) -> bool:
    try:
        return _cfg.getboolean(section, option)
    except Exception:
        return default


def _get_path(section: str, option: str, default_rel: Path) -> str:
    raw = _get_str(section, option, str(default_rel))
    p = Path(raw)
    if not p.is_absolute():
        p = BASE_DIR / p
    return str(p)

PLAYERS_MODEL_PATH = _get_path("paths", "players_model", MODELS_DIR / "FootballElementsYolo8s.pt")
PITCH_KP_WEIGHTS = _get_path("paths", "pitch_kp_model", MODELS_DIR / "pitch_640.pt")
PITCH_IMG_PATH = _get_path("paths", "pitch_image", PITCH_DIR / "pitch.png")
PITCH_CSV_PATH = _get_path("paths", "pitch_points_csv", PITCH_DIR / "pitch_points2.csv")

# ---------------------------------------------------------------------------
# Pitch / homografia
# ---------------------------------------------------------------------------

PITCH_IMGSZ = _get_int("pitch", "imgsz", 640)
PITCH_CONF = _get_float("pitch", "conf", 0.5)
PITCH_KP_CONF = _get_float("pitch", "kp_conf", 0.5)
PITCH_EMA_FACTOR = _get_float("pitch", "ema_factor", 0.9)

# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------

TRACK_STRONG_COLOR_MARGIN = _get_float("tracking", "strong_color_margin", 0.35)
TRACK_WEAK_COLOR_PENALTY = _get_float("tracking", "weak_color_penalty", 1.5)
TRACK_MARGIN_MIN = _get_float("tracking", "margin_min", 6.0)
TRACK_PROX_FACTOR = _get_float("tracking", "prox_factor", 1.5)
REF_TEAM_OVERRULE_FACTOR = _get_float("tracking", "referee_overrule_factor", 0.7)


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
KMEANS_MERGE_DELTA_AB = _get_float("colors", "kmeans_merge_delta_ab", 6.0)
EMD_L_WEIGHT          = _get_float("colors", "emd_l_weight", 0.2)
# ---------------------------------------------------------------------------
# Quality filter – [quality_filter]
# ---------------------------------------------------------------------------

QF_MIN_STABLE_FRAMES = _get_int("quality_filter", "min_stable_frames", 5)
QF_MAX_DELTA01 = _get_float("quality_filter", "max_delta01", 0.08)
QF_USE_QUALITY_ONLY = _get_bool("quality_filter", "use_quality_only", True)

# ---------------------------------------------------------------------------
# Wizualizacja – 2D mapy / heatmapy
# ---------------------------------------------------------------------------

MAP_WIDTH = _get_int("visualization.maps2d", "width", 600)
MAP_HEIGHT = _get_int("visualization.maps2d", "height", 350)
MAP_DOT_RADIUS = _get_int("visualization.maps2d", "dot_radius", 8)
MAP_LABEL_SCALE = _get_float("visualization.maps2d", "label_scale", 0.5)
MAP_GK_THICKNESS = _get_int("visualization.maps2d", "gk_outline_thickness", 2)

HM_BINS_W = _get_int("visualization.heatmaps", "bins_w", 64)
HM_BINS_H = _get_int("visualization.heatmaps", "bins_h", 44)
HM_GAUSS_BLUR_K = _get_int("visualization.heatmaps", "gauss_blur_k", 7)
HM_ALPHA_OVERLAY = _get_float("visualization.heatmaps", "alpha_overlay", 0.55)
HM_MIN_SAMPLES = _get_int("visualization.heatmaps", "min_samples", 5)
HM_USE_QUALITY_ONLY = _get_bool(
    "visualization.heatmaps", "use_quality_only", True
)

# ---------------------------------------------------------------------------
# Replay / logging
# ---------------------------------------------------------------------------

REPLAY_BUFFER_SIZE_FRAMES = _get_int("replay", "buffer_size_frames", 300)
LOG_ENABLE_POSITIONS = _get_bool("logging", "enable_positions_logging", True)
LOG_ENABLE_ANNOTATIONS = _get_bool("logging", "enable_annotations_logging", True)

# ---------------------------------------------------------------------------
# Główna klasa Settings używana w main/pipeline
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    """
    Konfiguracja konkretnego uruchomienia analizy (ścieżki + kilka parametrów).
    """
    model_path: str
    video_path: str
    output_path: str
    frames_dir: str = str(BASE_DIR / "Outputs")

    MARGIN_MIN: float = TRACK_MARGIN_MIN
    BASE_HOLD_SEC: float = 1.0
    PROX_FACTOR: float = TRACK_PROX_FACTOR

    show_preview: bool = False
    show_minimap: bool = False
