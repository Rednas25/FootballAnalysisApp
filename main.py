import sys
import os
from pathlib import Path
from urllib.parse import unquote
import threading
from datetime import datetime
import re
from collections import defaultdict
import csv
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Slot, Signal, QTimer, Property
from PySide6.QtQuick import QQuickImageProvider
import shutil
import supervision as sv
import cv2
from core import (analysis_maps as am, replay_overlays as ro,
    Settings, YoloRunner, JerseyColorExtractor, run_single_role, VideoPipeline,)
from core.config import (PLAYERS_MODEL_PATH)

class ReplayImageProvider(QQuickImageProvider):
    """
    Udostępnia ostatnią klatkę oraz minimapę jako QImage w pamięci.
    QML używa tego przez URL:
      - image://replay/frame?f=N
      - image://replay/minimap?f=N
    """

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self._frame_image = QImage()
        self._minimap_image = QImage()

    def set_frame_image(self, image: QImage):
        self._frame_image = image

    def set_minimap_image(self, image: QImage):
        self._minimap_image = image

    def clear_minimap(self):
        self._minimap_image = QImage()

    def requestImage(self, id, size, requestedSize):
        """
        id: np. "frame?f=10" albo "minimap?f=10"
        """
        if isinstance(id, str) and id.startswith("minimap"):
            img = self._minimap_image
        else:
            img = self._frame_image

        if img.isNull():
            empty = QImage(640, 360, QImage.Format_RGB32)
            empty.fill(0xFF000000)
            if size is not None:
                size.setWidth(empty.width())
                size.setHeight(empty.height())
            return empty

        if size is not None:
            size.setWidth(img.width())
            size.setHeight(img.height())
        return img


# --------------------------------- BACKEND -----------------------------------

class Backend(QObject):
    rolePreviewColorsChanged = Signal(str, list)
    analysisStarted = Signal()
    analysisFinished = Signal()
    analysisProgress = Signal(int)
    replayFramePathChanged = Signal()
    replayPositionChanged = Signal(float)
    selectionRangeChanged = Signal()
    avgPositionsImagePathChanged = Signal()
    heatmapImagePathChanged = Signal()
    heatmapLabelChanged = Signal()
    minimapImagePathChanged = Signal()
    analysisFinishedWithDir = Signal(str)
    analysisFrameInfo = Signal(int, int)

    def __init__(self, image_provider: ReplayImageProvider):
        super().__init__()
        self.video_path = ""
        self.extractor = JerseyColorExtractor()
        self.team_model = {}
        self.pipeline = None
        self.analysis_running = False
        self.replay_dir = ""
        self._last_run_dir = ""
        self._image_provider = image_provider
        # --- REPLAY ---
        self._replay_video_path = ""
        self._replay_cap = None
        self._replay_annotations = {}
        self._replay_kp = {}
        self._replay_positions = {}
        self._replay_total_frames = 0
        self._replay_fps = 25.0
        self._replay_frame_idx = 0
        self._replay_running = False
        self._replay_timer = QTimer(self)
        self._replay_timer.timeout.connect(self._on_replay_tick)

        # minimapa (2D map) – stan
        self._show_minimap_replay = False
        self._pitch_minimap = None        # cv2 obraz boiska dla minimapy
        self._minimap_image_path = ""     # URL dla QML: image://replay/minimap?f=N

        # Flagi do włączania / wyłączania annotacji (global)
        self._show_labels_global = True
        self._show_triangles_global = True
        self._show_kp = True  # pitch keypoints

        # Flagi per-team dla labeli i trójkątów
        self._lab_teamA = True
        self._lab_teamB = True
        self._lab_ref = True

        self._tri_teamA = True
        self._tri_teamB = True
        self._tri_ref = True

        self._selection_start_frame = 1
        self._selection_end_frame = 1
        self._selection_start_norm = 0.0
        self._selection_end_norm = 1.0

        # URL używany w QML
        self._replay_frame_path = ""
        project_root = Path(__file__).parent
        default_png = project_root / "assets/gui_files/background_load.png"
        if default_png.is_file():
            self._replay_frame_path = "file:///" + str(default_png).replace(os.sep, "/")

        self._avg_positions_image_path = ""
        self._heatmap_images = []
        self._heatmap_index = -1
        self._heatmap_image_path = ""
        self._heatmap_label = ""

        try:
            self._team_colors_replay = dict(am.TEAM_COLORS)
        except Exception:
            self._team_colors_replay = {}

    # -------------------------- Helpery ogólne --------------------------

    def _normalize_path(self, url: str) -> str:
        if url.startswith("file:///"):
            return unquote(url[8:])
        if url.startswith("file://"):
            return unquote(url[7:])
        return url

    @Slot(str)
    def setVideoPath(self, path: str):
        self.video_path = self._normalize_path(path)
        print("[Backend] Wybrany plik wideo:", self.video_path)

    @Property(str, notify=replayFramePathChanged)
    def replayFramePath(self) -> str:
        return self._replay_frame_path

    @Property(float, notify=replayPositionChanged)
    def replayPosition(self) -> float:
        if self._replay_total_frames <= 1:
            return 0.0
        return float(self._replay_frame_idx - 1) / float(self._replay_total_frames - 1)

    @Property(str, notify=avgPositionsImagePathChanged)
    def avgPositionsImagePath(self) -> str:
        return self._avg_positions_image_path

    def _set_avg_positions_image(self, path):
        if path:
            url = "file:///" + str(path).replace(os.sep, "/")
        else:
            url = ""
        self._avg_positions_image_path = url
        self.avgPositionsImagePathChanged.emit()

    @Slot()
    def hideAvgPositionsPreview(self):
        self._set_avg_positions_image(None)

    @Slot()
    def stopAnalysis(self):
        if self.pipeline is not None:
            try:
                self.pipeline.request_stop()
                print("[Backend] Stop requested")
            except Exception as e:
                print("[Backend] stopAnalysis error:", e)
        else:
            print("[Backend] stopAnalysis: pipeline is None")

    # --- Podgląd HEATMAP (wiele obrazków z możliwością przewijania) ---

    @Property(str, notify=heatmapImagePathChanged)
    def heatmapImagePath(self) -> str:
        return self._heatmap_image_path

    @Property(str, notify=heatmapLabelChanged)
    def heatmapLabel(self) -> str:
        return self._heatmap_label

    def _set_heatmap_image(self, path: Path | None, label: str = "") -> None:
        """Ustaw ścieżkę obrazka heatmapy + opis i wyślij sygnały do QML."""
        if path is not None:
            url = "file:///" + str(path).replace(os.sep, "/")
        else:
            url = ""

        changed = (url != self._heatmap_image_path) or (label != self._heatmap_label)
        self._heatmap_image_path = url
        self._heatmap_label = label

        if changed:
            self.heatmapImagePathChanged.emit()
            self.heatmapLabelChanged.emit()

    def _heatmap_label_from_path(self, p: Path) -> str:
        """
        Buduje czytelną etykietę z nazwy pliku overlayu.
        Przykładowe nazwy:
          TEAM_A_7_f170-672_overlay.png   ->  TEAM A #7
          TEAM_B_f170-672_overlay.png     ->  TEAM B
          ALL_PLAYERS_f170-672_overlay.png -> ALL PLAYERS
        """
        name = p.stem  # bez .png
        if name.endswith("_overlay"):
            name = name[:-8]

        # odcinamy część z zakresem klatek
        if "_f" in name:
            main, _rng = name.split("_f", 1)
        else:
            main = name

        main_up = main.upper()

        if main_up.startswith("TEAM_A_"):
            try:
                num = main.split("_")[-1]
                return f"TEAM A #{num}"
            except Exception:
                return "TEAM A"
        if main_up.startswith("TEAM_B_"):
            try:
                num = main.split("_")[-1]
                return f"TEAM B #{num}"
            except Exception:
                return "TEAM B"
        if main_up == "TEAM_A":
            return "TEAM A"
        if main_up == "TEAM_B":
            return "TEAM B"
        if main_up.startswith("ALL_PLAYERS"):
            return "ALL PLAYERS"
        return main

    @Slot()
    def hideHeatmapPreview(self) -> None:
        self._heatmap_images = []
        self._heatmap_index = -1
        self._set_heatmap_image(None, "")

    @Slot()
    def nextHeatmap(self) -> None:
        if not self._heatmap_images:
            return
        self._heatmap_index = (self._heatmap_index + 1) % len(self._heatmap_images)
        p = self._heatmap_images[self._heatmap_index]
        self._set_heatmap_image(p, self._heatmap_label_from_path(p))

    @Slot()
    def prevHeatmap(self) -> None:
        if not self._heatmap_images:
            return
        self._heatmap_index = (self._heatmap_index - 1) % len(self._heatmap_images)
        self._heatmap_index %= len(self._heatmap_images)
        p = self._heatmap_images[self._heatmap_index]
        self._set_heatmap_image(p, self._heatmap_label_from_path(p))

    # --- Minimap (2D mapka dla podglądu) ---

    def _init_team_colors_from_annotations(self):
        colors = {}

        anns_by_frame = self._replay_annotations or {}
        for frame_idx, anns in anns_by_frame.items():
            for ann in anns:
                text = (ann.get("text") or "").lower()
                col = ann.get("label_color") or ann.get("tri_color")
                if not col:
                    continue

                if "team a" in text:
                    key = "TEAM A"
                elif "team b" in text:
                    key = "TEAM B"
                else:
                    continue

                if key not in colors:
                    colors[key] = col

        base_default = dict(getattr(am, "TEAM_COLORS", {}))

        if colors:
            base_default.update(colors)
            print("[Backend] Team colors from annotations:", base_default)
        else:
            print("[Backend] Team colors from annotations: not found, using defaults:", base_default)

        self._team_colors_replay = base_default


    @Property(str, notify=minimapImagePathChanged)
    def minimapImagePath(self) -> str:
        return self._minimap_image_path

    def _ensure_pitch_minimap(self):
        if self._pitch_minimap is not None:
            return
        project_root = Path(__file__).parent
        pitch_path = project_root / "assets" / "pitch" / "pitch.png"
        img = cv2.imread(str(pitch_path))
        if img is None:
            print("[Backend] Minimap: nie mogę wczytać pitch.png:", pitch_path)
            self._pitch_minimap = None
        else:
            self._pitch_minimap = img

    def _load_positions_for_minimap(self, csv_path: str):
        """
        Ładowanie pozycji do minimapy: frame -> [(x01, y01, team, number), ...]
        number może być None, jeśli nie uda się sparsować.
        """
        mapping = defaultdict(list)
        if not os.path.isfile(csv_path):
            print(f"[Backend] Minimap: positions CSV not found: {csv_path}")
            return mapping

        with open(csv_path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            has_quality = "quality_ok" in (r.fieldnames or [])

            for row in r:
                # numer klatki
                try:
                    frame_idx = int(row.get("frame") or row.get("frame_idx") or 0)
                except Exception:
                    continue

                # filtr jakości
                if has_quality:
                    try:
                        if int(row["quality_ok"]) != 1:
                            continue
                    except Exception:
                        pass

                # pozycja 0–1
                try:
                    x01 = float(row["x01"])
                    y01 = float(row["y01"])
                except Exception:
                    continue

                if not (0.0 <= x01 <= 1.0 and 0.0 <= y01 <= 1.0):
                    continue

                # drużyna
                team = (row.get("team") or "").strip().upper()

                # numer zawodnika
                number = None
                try:
                    num_str = (row.get("number") or "").strip()
                    if num_str != "":
                        number = int(num_str)
                except Exception:
                    number = None

                mapping[frame_idx].append((x01, y01, team, number))

        return mapping

    def _update_minimap_for_frame(self, frame_idx: int):
        """
        Rysuje 2D mapę w pamięci i aktualizuje obraz przez image provider.
        Styl zbliżony do avg_positions_map:
        - większe kropki,
        - numer zawodnika w środku,
        - kolory jak dla drużyn z avg_positions_map.TEAM_COLORS.
        """
        if not self._show_minimap_replay:
            # wyłączone – czyścimy URL i obraz
            if self._minimap_image_path != "":
                self._minimap_image_path = ""
                self.minimapImagePathChanged.emit()
            self._image_provider.clear_minimap()
            return

        self._ensure_pitch_minimap()
        if self._pitch_minimap is None:
            return

        pts = self._replay_positions.get(frame_idx, [])
        img = self._pitch_minimap.copy()
        h, w = img.shape[:2]

        try:
            team_colors = self._team_colors_replay or dict(am.TEAM_COLORS)
        except Exception:
            team_colors = {}

        dot_radius = 28
        label_scale = 1

        for item in pts:
            if len(item) == 4:
                x01, y01, team, number = item
            else:
                x01, y01, team = item
                number = None

            px = int(x01 * (w - 1))
            py = int(y01 * (h - 1))

            team_up = (team or "").upper()

            # kolor – próbujemy z TEAM_COLORS, fallback dla sędziego i nieznanych
            if "REF" in team_up:
                col = (0, 255, 255)  # żółty dla sędziego
            else:
                col = team_colors.get(team_up, None)
                if col is None:
                    # nieznany - biały
                    col = (255, 255, 255)

            cv2.circle(img, (px, py), dot_radius, col, -1, lineType=cv2.LINE_AA)

            # numer w środku kropki (jeśli znamy)
            if number is not None:
                label = str(number)
                (tw, th), _ = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, label_scale, 2
                )
                tx = int(px - tw / 2)
                ty = int(py + th / 2)

                cv2.putText(
                    img,
                    label,
                    (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    label_scale,
                    (0, 0, 0),
                    3,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    img,
                    label,
                    (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    label_scale,
                    (255, 255, 255),
                    3,
                    cv2.LINE_AA,
                )

        # konwersja na QImage
        try:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print("[Backend] _update_minimap_for_frame: błąd cvtColor:", e)
            return

        h2, w2, ch = rgb.shape
        bytes_per_line = ch * w2
        qimg = QImage(rgb.data, w2, h2, bytes_per_line, QImage.Format_RGB888).copy()

        self._image_provider.set_minimap_image(qimg)

        url = f"image://replay/minimap?f={frame_idx}"
        if url != self._minimap_image_path:
            self._minimap_image_path = url
            self.minimapImagePathChanged.emit()

    @Slot(bool)
    def setReplayMinimapEnabled(self, enabled: bool):
        """
        Włącza / wyłącza 2D mapę w trybie replay (guzik '2D Map').
        """
        self._show_minimap_replay = bool(enabled)
        if not enabled:
            self._image_provider.clear_minimap()
            if self._minimap_image_path != "":
                self._minimap_image_path = ""
                self.minimapImagePathChanged.emit()
        else:
            if self._replay_frame_idx > 0:
                self._update_minimap_for_frame(self._replay_frame_idx)

    # -------------------------- replay position emit --------------------------

    def _emit_replay_position(self):
        try:
            self.replayPositionChanged.emit(self.replayPosition)
        except Exception as e:
            print("[Backend] problem z replayPositionChanged:", e)

    @Slot(float)
    def seekReplayToPosition(self, norm: float):
        if self._replay_total_frames <= 0:
            print("[Backend] seekReplayToPosition: brak sesji replay")
            return

        try:
            norm = float(norm)
        except (TypeError, ValueError):
            norm = 0.0

        if norm < 0.0:
            norm = 0.0
        if norm > 1.0:
            norm = 1.0

        frame_idx = 1 + int(norm * (self._replay_total_frames - 1))
        print(f"[Backend] seekReplayToPosition: norm={norm:.3f} -> frame {frame_idx}")
        self._seek_replay_frame(frame_idx)

    @Slot(bool, bool)
    def generateAveragePositions(self, teamA: bool, teamB: bool):
        if not self.replay_dir:
            print("[Backend] generateAveragePositions: replay_dir nieustawiony (najpierw Load Outputs).")
            return

        dir_path = Path(self.replay_dir)
        csv_path = dir_path / "positions_stream.csv"
        if not csv_path.is_file():
            print("[Backend] generateAveragePositions: brak positions_stream.csv w", csv_path)
            return

        # które drużyny uwzględniamy
        allowed = []
        if teamA:
            allowed.append("TEAM A")
        if teamB:
            allowed.append("TEAM B")
        if not allowed:
            print("[Backend] generateAveragePositions: żadna drużyna nie zaznaczona (TEAM A/B).")
            return

        # zakres klatek z selektora
        start_frame = int(self._selection_start_frame)
        end_frame = int(self._selection_end_frame)
        if end_frame < start_frame:
            start_frame, end_frame = end_frame, start_frame

        analysis_dir = dir_path / f"analysis_{start_frame}-{end_frame}"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        print(f"[Backend] Average positions: frames {start_frame}-{end_frame}, teams={allowed}")
        try:
            data = am.load_positions(
                str(csv_path),
                use_quality_only=True,
                frame_min=start_frame,
                frame_max=end_frame,
                allowed_teams=allowed,
            )
        except Exception as e:
            print("[Backend] generateAveragePositions: błąd load_positions:", e)
            return

        means = am.compute_means(data, min_samples=5)
        print(f"[Backend] Average positions: policzono dla {len(means)} zawodników.")

        if not means:
            print("[Backend] generateAveragePositions: brak danych po filtrach (nic do zapisania).")
            return

        # Ścieżka do pitch.png
        project_root = Path(__file__).parent
        pitch_path = project_root / "assets" / "pitch" / "pitch.png"

        pitch_img = am.load_pitch_image(str(pitch_path), size_wh=(am.MAP_WIDTH, am.MAP_HEIGHT))
        try:
            team_colors = self._team_colors_replay or dict(am.TEAM_COLORS)
        except Exception:
            team_colors = getattr(am, "TEAM_COLORS", {})
        result_img = am.draw_means_on_pitch(pitch_img, means, team_colors)

        if teamA and not teamB:
            suffix = "_TeamA"
        elif teamB and not teamA:
            suffix = "_TeamB"
        else:
            suffix = ""

        out_img = analysis_dir / f"avg_positions_map{suffix}.png"
        out_csv = analysis_dir / f"avg_positions{suffix}.csv"

        am.save_means_csv(means, str(out_csv))
        cv2.imwrite(str(out_img), result_img)

        print(f"[Backend] Average positions: zapisano mapkę: {out_img}")
        print(f"[Backend] Average positions: zapisano CSV: {out_csv}")
        self._set_avg_positions_image(out_img)

    # ------------------------------------------------------------------
    # HEATMAPY
    # ------------------------------------------------------------------
    def _load_positions_for_heatmaps(self, csv_path: str,
                                     frame_min: int,
                                     frame_max: int,
                                     use_quality_only: bool = True):
        """
        Wczytuje positions_stream.csv z filtrem po numerach klatek.
        Zwraca:
            data[(team, number)] = lista (x01, y01)
            teams[team] = zbiór (team, number)
        """
        data = defaultdict(list)
        teams = defaultdict(set)

        with open(csv_path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            has_quality = "quality_ok" in (r.fieldnames or [])

            for row in r:
                try:
                    frame_idx = int(row.get("frame") or row.get("frame_idx") or 0)
                except Exception:
                    frame_idx = 0

                if frame_idx < frame_min or frame_idx > frame_max:
                    continue

                if use_quality_only and has_quality:
                    try:
                        if int(row["quality_ok"]) != 1:
                            continue
                    except Exception:
                        pass

                try:
                    team = row["team"].strip()
                    number = int(row["number"])
                    x01 = float(row["x01"])
                    y01 = float(row["y01"])
                except Exception:
                    continue

                if not (0.0 <= x01 <= 1.0 and 0.0 <= y01 <= 1.0):
                    continue

                key = (team, number)
                data[key].append((x01, y01))
                teams[team].add(key)

        return data, teams

    @Slot(list, list, bool, bool, bool)
    def generateHeatmaps(self,
                         playersA, playersB,
                         groupTeamA: bool,
                         groupTeamB: bool,
                         groupAll: bool):
        """
        Generuje heatmapy:
        - osobne dla każdego zaznaczonego zawodnika (playersA / playersB),
        - grupowe, jeśli zaznaczone: TEAM A, TEAM B, ALL PLAYERS.

        Dane bierzemy z positions_stream.csv w bieżącym replay_dir,
        dodatkowo filtrując po zaznaczonym frame range (selectionStart/End).

        ZAPIS:
            [replay_dir]/analysis_<start>-<end>/homography/players
            [replay_dir]/analysis_<start>-<end>/homography/teams
            [replay_dir]/analysis_<start>-<end>/homography/overall
        """
        if not self.replay_dir:
            print("[Backend] generateHeatmaps: replay_dir nieustawiony (najpierw Load Outputs).")
            return

        dir_path = Path(self.replay_dir)
        csv_path = dir_path / "positions_stream.csv"
        if not csv_path.is_file():
            print("[Backend] generateHeatmaps: brak positions_stream.csv w", csv_path)
            return

        # zakres klatek
        start_frame = int(self._selection_start_frame)
        end_frame = int(self._selection_end_frame)
        if end_frame < start_frame:
            start_frame, end_frame = end_frame, start_frame

        # listy z QML -> sety intów
        try:
            playersA = {int(x) for x in (playersA or [])}
            playersB = {int(x) for x in (playersB or [])}
        except Exception:
            playersA, playersB = set(), set()

        print(f"[Backend] Heatmaps: frames {start_frame}-{end_frame}, "
              f"playersA={sorted(playersA)}, playersB={sorted(playersB)}, "
              f"groupA={groupTeamA}, groupB={groupTeamB}, all={groupAll}")

        use_quality = getattr(am, "USE_QUALITY_ONLY", True)
        try:
            data, teams = self._load_positions_for_heatmaps(
                str(csv_path),
                frame_min=start_frame,
                frame_max=end_frame,
                use_quality_only=use_quality,
            )
        except Exception as e:
            print("[Backend] generateHeatmaps: błąd wczytywania pozycji:", e)
            return

        if not data:
            print("[Backend] generateHeatmaps: brak danych w wybranym zakresie klatek.")
            return

        # katalog jak przy average positions: analysis_<start>-<end>
        analysis_dir = dir_path / f"analysis_{start_frame}-{end_frame}"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        # podfolder homography/...
        heatmaps_root = analysis_dir / "homography"
        per_player_dir = heatmaps_root / "players"
        per_team_dir = heatmaps_root / "teams"
        overall_dir = heatmaps_root / "overall"
        per_player_dir.mkdir(parents=True, exist_ok=True)
        per_team_dir.mkdir(parents=True, exist_ok=True)
        overall_dir.mkdir(parents=True, exist_ok=True)

        # obraz boiska
        project_root = Path(__file__).parent
        pitch_path = project_root / "assets" / "pitch" / "pitch.png"
        pitch_img = am.load_pitch_image(str(pitch_path),
                                        size_wh=(am.MAP_WIDTH, am.MAP_HEIGHT))

        min_samples = getattr(am, "MIN_SAMPLES", 5)

        # --- HEATMAPY PER ZAWODNIK ---
        saved_players = 0
        for (team, num), pts in data.items():
            if team.strip().upper().startswith("TEAM A"):
                if num not in playersA:
                    continue
            elif team.strip().upper().startswith("TEAM B"):
                if num not in playersB:
                    continue
            else:
                continue

            if len(pts) < min_samples:
                continue

            hm_arr = am.hist2d_pitch01(pts, bins=am.HM_BINS)
            safe_team = team.replace(" ", "_")
            base = per_player_dir / f"{safe_team}_{num}_f{start_frame}-{end_frame}"
            am.save_npz_png(hm_arr, str(base), pitch_img)
            saved_players += 1

        print(f"[Backend] Heatmaps: zapisano {saved_players} heatmap zawodników → {per_player_dir}")

        # --- HEATMAPY DRUŻYNOWE ---
        if groupTeamA and "TEAM A" in teams:
            all_pts = []
            for key in teams["TEAM A"]:
                all_pts.extend(data.get(key, []))
            if len(all_pts) >= min_samples:
                hm_team = am.hist2d_pitch01(all_pts, bins=am.HM_BINS)
                base = per_team_dir / f"TEAM_A_f{start_frame}-{end_frame}"
                am.save_npz_png(hm_team, str(base), pitch_img)
                print(f"[Backend] Heatmaps: TEAM A → {base}")

        if groupTeamB and "TEAM B" in teams:
            all_pts = []
            for key in teams["TEAM B"]:
                all_pts.extend(data.get(key, []))
            if len(all_pts) >= min_samples:
                hm_team = am.hist2d_pitch01(all_pts, bins=am.HM_BINS)
                base = per_team_dir / f"TEAM_B_f{start_frame}-{end_frame}"
                am.save_npz_png(hm_team, str(base), pitch_img)
                print(f"[Backend] Heatmaps: TEAM B → {base}")

        # --- HEATMAPA GLOBALNA ---
        if groupAll:
            all_pts_global = []
            for pts in data.values():
                all_pts_global.extend(pts)
            if len(all_pts_global) >= min_samples:
                hm_all = am.hist2d_pitch01(all_pts_global, bins=am.HM_BINS)
                base = overall_dir / f"ALL_PLAYERS_f{start_frame}-{end_frame}"
                am.save_npz_png(hm_all, str(base), pitch_img)
                print(f"[Backend] Heatmaps: ALL PLAYERS → {base}")

        # --- Podgląd heatmap po wygenerowaniu ---
        overlays = []
        for subdir in (per_player_dir, per_team_dir, overall_dir):
            if subdir.is_dir():
                overlays.extend(sorted(subdir.glob("*_overlay.png")))

        self._heatmap_images = overlays

        if overlays:
            self._heatmap_index = 0
            first = overlays[0]
            self._set_heatmap_image(first, self._heatmap_label_from_path(first))
            print(f"[Backend] Heatmap preview: {len(overlays)} plików overlay.")
        else:
            self._heatmap_index = -1
            self._set_heatmap_image(None, "")
            print("[Backend] Heatmap preview: brak plików overlay.")

        print("[Backend] Heatmaps: gotowe.")

    @Slot(str)
    def setReplayDirectory(self, url: str):
        path = self._normalize_path(url)
        if os.path.isdir(path):
            self.replay_dir = path
            print("[Backend] Wybrany katalog replay:", self.replay_dir)
            self._set_avg_positions_image(None)
            self.hideHeatmapPreview()
            self._init_replay_session()
        else:
            print("[Backend] Podana ścieżka nie jest katalogiem:", path)

    @Slot(float, float)
    def setSelectionRange(self, startNorm: float, endNorm: float):
        """
        Ustawia zakres zaznaczenia na podstawie wartości 0.0–1.0 z RangeSlidera.
        Przelicza to na numery klatek i zapamiętuje.
        """
        try:
            s = float(startNorm)
            e = float(endNorm)
        except (TypeError, ValueError):
            s, e = 0.0, 1.0

        if s < 0.0:
            s = 0.0
        if e > 1.0:
            e = 1.0
        if e < s:
            s, e = e, s  # pilnujemy, żeby start <= end

        self._selection_start_norm = s
        self._selection_end_norm = e

        if self._replay_total_frames <= 0:
            print(f"[Backend] setSelectionRange: brak sesji replay, zapisano normy {s:.3f}–{e:.3f}")
            return

        self._selection_start_frame = 1 + int(s * (self._replay_total_frames - 1))
        self._selection_end_frame = 1 + int(e * (self._replay_total_frames - 1))
        self.selectionRangeChanged.emit()

    @Property(int, notify=selectionRangeChanged)
    def selectionStartFrame(self) -> int:
        return int(self._selection_start_frame)

    @Property(int, notify=selectionRangeChanged)
    def selectionEndFrame(self) -> int:
        return int(self._selection_end_frame)

    @Slot(int)
    def skipReplayFrames(self, frames: int):
        """
        Skacze o podaną liczbę klatek (frames może być ujemne).
        Np. -48 = 48 klatek w lewo, +48 = w prawo.
        """
        if self._replay_total_frames <= 0:
            print("[Backend] skipReplayFrames: brak sesji replay")
            return

        try:
            delta = int(frames)
        except (TypeError, ValueError):
            delta = 0

        if delta == 0:
            return

        current = self._replay_frame_idx if self._replay_frame_idx > 0 else 1
        target = current + delta
        if target < 1:
            target = 1
        if target > self._replay_total_frames:
            target = self._replay_total_frames

        print(f"[Backend] skipReplayFrames: current={current}, delta={delta} -> target={target}")
        self._seek_replay_frame(target)

    @Slot(result=str)
    def getOutputsRoot(self) -> str:
        project_root = Path(__file__).parent
        outputs_root = project_root / "Outputs"
        return str(outputs_root)

    # -------------------------- Sterowanie overlay --------------------------

    def _ann_group(self, ann: dict) -> str:
        """
        Przypisuje annotation do grupy: 'teamA', 'teamB', 'ref', 'unknown'
        na podstawie label_text (np. 'TEAM A #7', 'referee #3', itp.)
        """
        text = (ann.get("text") or "").lower()
        if text.startswith("referee"):
            return "ref"
        if "team a" in text:
            return "teamA"
        if "team b" in text:
            return "teamB"
        return "unknown"

    def _should_show_tri(self, ann: dict) -> bool:
        if not self._show_triangles_global:
            return False
        group = self._ann_group(ann)
        if group == "teamA":
            return self._tri_teamA
        if group == "teamB":
            return self._tri_teamB
        if group == "ref":
            return self._tri_ref
        return True

    def _should_show_label(self, ann: dict) -> bool:
        if not self._show_labels_global:
            return False
        group = self._ann_group(ann)
        if group == "teamA":
            return self._lab_teamA
        if group == "teamB":
            return self._lab_teamB
        if group == "ref":
            return self._lab_ref
        return True

    @Slot(bool)
    def setShowKeypoints(self, enabled: bool):
        self._show_kp = bool(enabled)
        if self._replay_frame_idx > 0:
            self._seek_replay_frame(self._replay_frame_idx)

    @Slot(bool)
    def setShowLabels(self, enabled: bool):
        self._show_labels_global = bool(enabled)
        if self._replay_frame_idx > 0:
            self._seek_replay_frame(self._replay_frame_idx)

    @Slot(bool)
    def setShowTriangles(self, enabled: bool):
        self._show_triangles_global = bool(enabled)
        if self._replay_frame_idx > 0:
            self._seek_replay_frame(self._replay_frame_idx)

    @Slot(bool, bool, bool)
    def setTrianglesFilter(self, teamA: bool, teamB: bool, referee: bool):
        """Ustawia, dla których grup rysować trójkąty (TEAM A/B, referee)."""
        self._tri_teamA = bool(teamA)
        self._tri_teamB = bool(teamB)
        self._tri_ref = bool(referee)
        if self._replay_frame_idx > 0:
            self._seek_replay_frame(self._replay_frame_idx)

    @Slot(bool, bool, bool)
    def setLabelsFilter(self, teamA: bool, teamB: bool, referee: bool):
        """Ustawia, dla których grup rysować labele (TEAM A/B, referee)."""
        self._lab_teamA = bool(teamA)
        self._lab_teamB = bool(teamB)
        self._lab_ref = bool(referee)
        if self._replay_frame_idx > 0:
            self._seek_replay_frame(self._replay_frame_idx)

    # -------------------------- Replay init / load --------------------------

    def _init_replay_session(self):
        if not self.replay_dir:
            print("[Backend] _init_replay_session: replay_dir pusty")
            return

        if self._replay_cap is not None:
            try:
                self._replay_cap.release()
            except Exception:
                pass
            self._replay_cap = None

        dir_path = Path(self.replay_dir)

        candidates = []
        for name in ("input_video.mp4", "team_labels.mp4"):
            cand = dir_path / name
            if cand.is_file():
                candidates.append(cand)
        if not candidates:
            for p in dir_path.glob("*.mp4"):
                candidates.append(p)
                break

        if not candidates:
            print("[Backend] Brak pliku .mp4 w katalogu replay:", dir_path)
            return

        video_path = str(candidates[0])
        self._replay_video_path = video_path
        print(f"[Backend] Replay video path: {self._replay_video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("[Backend] Nie można otworzyć wideo do replay:", video_path)
            return

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

        self._replay_total_frames = total
        self._replay_fps = fps
        self._replay_frame_idx = 0

        cap.release()
        self._replay_cap = None

        ann_path = dir_path / "annotations_stream.csv"
        kp_path = dir_path / "pitch_keypoints_stream.csv"
        pos_path = dir_path / "positions_stream.csv"

        self._replay_annotations = ro.load_annotations(str(ann_path))
        self._init_team_colors_from_annotations()
        self._replay_kp = ro.load_pitch_kp(str(kp_path))
        self._replay_positions = self._load_positions_for_minimap(str(pos_path))

        # reset minimapy dla nowej sesji
        self._image_provider.clear_minimap()
        self._minimap_image_path = ""
        self.minimapImagePathChanged.emit()

        print(f"[Backend] Replay init: video={video_path}, frames={total}, fps={fps}")

        # po resecie ustaw pozycję timeline’u na początek
        self._emit_replay_position()

        if self._replay_total_frames > 0:
            self._seek_replay_frame(1)

    # -------------------------- LOGIKA REPLAY (in-memory) --------------------------

    def _render_replay_frame(self, frame_idx: int, frame):
        """
        Rysuje annotacje na podanej klatce i wysyła ją do QML przez ReplayImageProvider.
        """
        if self._replay_total_frames <= 0:
            return

        frame_idx = max(1, min(self._replay_total_frames, int(frame_idx)))

        anns_all = self._replay_annotations.get(frame_idx, []) or []
        kpf = self._replay_kp.get(frame_idx, []) or []

        # --- TRIANGLES LAYER ---
        if self._show_triangles_global:
            tri_anns = [ann for ann in anns_all if self._should_show_tri(ann)]
        else:
            tri_anns = []

        # --- LABELS LAYER ---
        if self._show_labels_global:
            lab_anns = [ann for ann in anns_all if self._should_show_label(ann)]
        else:
            lab_anns = []

        # 1) rysujemy trójkąty
        if tri_anns:
            frame = ro.draw_overlays(
                frame,
                tri_anns,
                pitch_kp_for_frame=None,
                show_labels=False,
                show_triangles=True,
                show_kp=False,
            )

        # 2) rysujemy labele + opcjonalnie pitch
        if lab_anns or (self._show_kp and kpf):
            frame = ro.draw_overlays(
                frame,
                lab_anns,
                kpf if self._show_kp else [],
                show_labels=self._show_labels_global,
                show_triangles=False,
                show_kp=self._show_kp,
            )

        # 3) konwersja z BGR (OpenCV) na RGB (QImage)
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print("[Backend] _render_replay_frame: błąd cvtColor:", e)
            return

        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()

        self._image_provider.set_frame_image(qimg)
        self._replay_frame_idx = frame_idx
        self._replay_frame_path = f"image://replay/frame?f={frame_idx}"
        self.replayFramePathChanged.emit()
        self._emit_replay_position()  # aktualizacja timeline’u po każdej klatce

        # 4) aktualizacja minimapy (jeśli włączona)
        if self._show_minimap_replay:
            self._update_minimap_for_frame(frame_idx)

    def _seek_replay_frame(self, frame_idx: int):
        """
        Przy seeku otwieramy nowe VideoCapture i odtwarzamy od początku do frame_idx.
        """
        if not self._replay_video_path or self._replay_total_frames <= 0:
            return

        frame_idx = max(1, min(self._replay_total_frames, int(frame_idx)))

        if self._replay_cap is not None:
            try:
                self._replay_cap.release()
            except Exception:
                pass
            self._replay_cap = None

        cap = cv2.VideoCapture(self._replay_video_path)
        if not cap.isOpened():
            print("[Backend] _seek_replay_frame: nie udało się otworzyć wideo:", self._replay_video_path)
            return

        self._replay_cap = cap
        current_idx = 1
        frame = None

        while current_idx <= frame_idx:
            ret, cur = cap.read()
            if not ret:
                print("[Backend] _seek_replay_frame: nie udało się odczytać klatki", current_idx)
                return
            frame = cur
            current_idx += 1

        self._render_replay_frame(frame_idx, frame)

    def _step_replay_frame(self) -> bool:
        """
        Przechodzi do kolejnej klatki podczas odtwarzania sekwencyjnego.
        """
        if self._replay_total_frames <= 0:
            return False

        if self._replay_cap is None:
            self._seek_replay_frame(1)
            return True

        if self._replay_frame_idx <= 0:
            self._seek_replay_frame(1)
            return True

        next_idx = self._replay_frame_idx + 1
        if next_idx > self._replay_total_frames:
            return False

        ret, frame = self._replay_cap.read()
        if not ret:
            print("[Backend] _step_replay_frame: nie udało się odczytać next_idx", next_idx)
            return False

        self._render_replay_frame(next_idx, frame)
        return True

    # -------------------------- Auto-play / timer --------------------------

    def _on_replay_tick(self):
        if not self._step_replay_frame():
            self._replay_timer.stop()
            self._replay_running = False
            print("[Backend] Replay stopped (koniec lub błąd)")

    @Slot()
    def toggleReplayAuto(self):
        if self._replay_running:
            self._replay_timer.stop()
            self._replay_running = False
            print("[Backend] Replay paused")
            return

        if self._replay_total_frames <= 0:
            print("[Backend] toggleReplayAuto: brak sesji replay")
            return

        interval_ms = int(1000 / max(1.0, self._replay_fps))
        self._replay_timer.start(interval_ms)
        self._replay_running = True
        print("[Backend] Replay started, interval:", interval_ms, "ms")

    # -------------------------- Team selector / analiza --------------------------

    def _select_role(self, key: str):
        if not self.video_path:
            print("Najpierw wybierz plik wideo (Load).")
            return

        print(f"[Backend] Start setup colors for: {key}, video={self.video_path}")
        model = run_single_role(self.video_path, self.extractor, key, top_m_for_proto=2)
        self.team_model[key] = model
        print(f"[Backend] Saved colors for: {key}")

        swatches = model.get("swatches_bgr") or []
        color_list = []
        for i in range(2):
            if i < len(swatches):
                b, g, r = swatches[i]
                color_hex = f"#{int(r):02X}{int(g):02X}{int(b):02X}"
            else:
                color_hex = "#FFFFFF"
            color_list.append(color_hex)

        print(f"[Backend] preview colors for {key} =", color_list)
        self.rolePreviewColorsChanged.emit(key, color_list)

    @Slot()
    def selectTeamAPlayerColor(self):
        self._select_role("teamA_player")

    @Slot()
    def selectTeamAGKColor(self):
        self._select_role("teamA_goalkeeper")

    @Slot()
    def selectTeamBPlayerColor(self):
        self._select_role("teamB_player")

    @Slot()
    def selectTeamBGKColor(self):
        self._select_role("teamB_goalkeeper")

    @Slot()
    def selectRefereeColor(self):
        self._select_role("referee")

    @Slot(bool)
    def setYoloPreview(self, enabled: bool):
        print(f"[Backend] setYoloPreview({enabled})")
        if self.pipeline is not None:
            self.pipeline.set_preview(enabled)

    @Slot(bool)
    def setMinimapPreview(self, enabled: bool):
        print(f"[Backend] setMinimapPreview({enabled})")
        if self.pipeline is not None:
            self.pipeline.set_minimap(enabled)

    @Slot(str)
    def startAnalysis(self, run_label: str):
        if not self.video_path:
            print("Wrong file")
            return

        if self.analysis_running:
            print("[Backend] Analysis already running")
            return

        if not self.team_model:
            print("Colors not selected")

        print("[Backend] Video analysis start")
        print(f"[Backend] Video name: '{run_label}'")

        self.analysis_running = True
        self.analysisStarted.emit()

        def worker():
            try:
                project_root = Path(__file__).parent

                model_path = Path(PLAYERS_MODEL_PATH)
                outputs_root = project_root / "Outputs"
                outputs_root.mkdir(parents=True, exist_ok=True)

                label = (run_label or "").strip()
                if not label:
                    label = Path(self.video_path).stem or "analysis"

                label_safe = re.sub(r"[^0-9A-Za-z._-]+", "_", label)
                if not label_safe:
                    label_safe = "analysis"

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                run_dir = outputs_root / f"{label_safe}_{ts}"
                run_dir.mkdir(parents=True, exist_ok=True)
                self._last_run_dir = str(run_dir)

                # ŚCIEŻKI WYJŚCIOWE
                output_path = run_dir / "team_labels.mp4"
                frames_dir = run_dir
                print("[Backend] Folders of analize:", run_dir)

                # KONFIG
                cfg = Settings(
                    model_path=str(model_path),
                    video_path=str(self.video_path),
                    output_path=str(output_path),
                    frames_dir=str(frames_dir),
                    MARGIN_MIN=6.0,
                    BASE_HOLD_SEC=1.0,
                    PROX_FACTOR=1.5,
                    show_preview=False,
                    show_minimap=False,
                )

                yolo = YoloRunner(
                    model_path=cfg.model_path,
                    device="auto",
                    imgsz=1280,
                    conf=0.4,
                )

                video_info = sv.VideoInfo.from_video_path(cfg.video_path)

                pipe = VideoPipeline(cfg, yolo, self.extractor, self.team_model, video_info)
                self.pipeline = pipe

                def progress_hook(pct: int):
                    try:
                        self.analysisProgress.emit(int(pct))
                    except Exception as e:
                        print("[Backend] problem z wysłaniem progresu:", e)

                def frame_info_hook(frame_idx: int, total_frames: int):
                    try:
                        self.analysisFrameInfo.emit(int(frame_idx), int(total_frames))
                    except Exception as e:
                        print("[Backend] problem z wysłaniem info o klatce:", e)

                frames_done = pipe.run(progress_cb=progress_hook, frame_cb=frame_info_hook,)

                # ------------- PRZYCINANIE input_video.mp4 -------------
                # Tworzymy przycięty plik wejściowy (od klatki 1 do frames_done)
                def _trim_video(src_path: str, dst_path: str, frames_to_keep: int) -> bool:
                    try:
                        cap = cv2.VideoCapture(src_path)
                        if not cap.isOpened():
                            print("[Backend] Trim: cannot open source:", src_path);
                            return False
                        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                        if w <= 0 or h <= 0:
                            ok, fr = cap.read()
                            if not ok:
                                cap.release();
                                return False
                            h, w = fr.shape[:2]
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        out = cv2.VideoWriter(str(dst_path), fourcc, fps, (w, h))
                        if not out.isOpened():
                            print("[Backend] Trim: cannot open writer:", dst_path)
                            cap.release();
                            return False

                        count = 0
                        while count < frames_to_keep:
                            ret, frame = cap.read()
                            if not ret:
                                break
                            out.write(frame)
                            count += 1

                        out.release()
                        cap.release()
                        print(f"[Backend] Trim: wrote {count} frames to {dst_path}")
                        return count > 0
                    except Exception as e:
                        print("[Backend] Trim error:", e)
                        return False

                # Wyjście: input_video.mp4 w folderze run’u
                trimmed_input_path = run_dir / "input_video.mp4"

                src = Path(self.video_path)
                if isinstance(frames_done, int) and frames_done > 0 and src.is_file():
                    _ = _trim_video(str(src), str(trimmed_input_path), frames_done)
                else:
                    print("[Backend] Trim skipped (no frames_done or missing source).")

                # ------------- KONIEC -------------
                print("[Backend] Analysis finished")
                print("[Backend]  - video:", output_path)
                print("[Backend]  - CSV / logs:", frames_dir)

            except Exception as e:
                import traceback
                print("[Backend] Error during analysis", e)
                traceback.print_exc()
            finally:
                self.analysisFinished.emit()
                self.pipeline = None
                self.analysis_running = False
            try:
                self.analysisFinishedWithDir.emit(self._last_run_dir or "")
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()


# ----------------------------------- main ------------------------------------

def main():
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    image_provider = ReplayImageProvider()
    engine.addImageProvider("replay", image_provider)

    backend = Backend(image_provider)
    engine.rootContext().setContextProperty("backend", backend)

    qml_root = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_root))

    qml_file = qml_root / "App.qml"
    engine.load(str(qml_file))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
