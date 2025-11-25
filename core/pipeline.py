import os, time, cv2, numpy as np, supervision as sv
from typing import Optional, Tuple, List, Dict
from core.visualization import (annotate_people_custom_labels, AnnotationLogger, PitchKPLogger,)
from core.pitch import (PitchKeypointsDetectorLB, load_template_norm_from_csv, HomographyEstimator, is_in_central_band, penalty_side,is_near_touchline,)
from core.config import (Settings, PITCH_KP_WEIGHTS, PITCH_IMGSZ, PITCH_CONF, PITCH_KP_CONF,PITCH_IMG_PATH, PITCH_CSV_PATH, PITCH_EMA_FACTOR,
                         MAP_WIDTH, MAP_HEIGHT, QF_MIN_STABLE_FRAMES, QF_MAX_DELTA01, TRACK_STRONG_COLOR_MARGIN, TRACK_WEAK_COLOR_PENALTY,)
from core.tracking.positions_logger import PositionsLogger
from core.tracking import TeamClassifier, Stabilizer, SquadIDManager

class VideoPipeline:
    def __init__(self, cfg: Settings, yolo, extractor, team_model, video_info: sv.VideoInfo):
        self.cfg = cfg
        self.yolo = yolo
        self.extractor = extractor
        self.team_model = team_model
        self.video_info = video_info

        self._stop_requested = False
        self._last_frame_idx = 0

        self.show_preview: bool = bool(getattr(cfg, "show_preview", True))
        self.show_minimap: bool = bool(getattr(cfg, "show_minimap", True))
        self._prev_show_preview = self.show_preview
        self._prev_show_minimap = self.show_minimap
        self._preview_window_created = False
        self._preview_window_name = 'YOLO Team Labeler'

        self._perf_stats = {
            "frames": 0,
            "frame_total": 0.0 ,
            "yolo_players": 0.0,  # czas YOLO dla detekcji zawodników
            "pitch_kp": 0.0,  # YOLO od keypointów + homografia + log keypoints
            "cpu_logic": 0.0,  # tracking, kolory, stabilizacja, SquadID, minimapa itd.
            "logging": 0.0,  # zapisy CSV (pos_logger, ann_logger) i inne I/O
        }

        self.squad = SquadIDManager(
            match_radius=0.005,
            ttl_frames=120,
            warmup_frames=3,
            expand_per_miss=0.0005,
            vel_alpha=0.0,
            team_switch_hold=3
        )

        self.referee_ids: set[int] = set()
        self.gk_ids: Dict[str, Optional[int]] = {"TEAM A": None, "TEAM B": None}

        self.pitch_kp = PitchKeypointsDetectorLB(
            weights_path=PITCH_KP_WEIGHTS,
            imgsz=PITCH_IMGSZ,
            conf=PITCH_CONF,
            kp_conf=PITCH_KP_CONF,
            device = getattr(self.yolo, "device", "auto"),
        )

        template_norm = load_template_norm_from_csv(PITCH_IMG_PATH, PITCH_CSV_PATH)
        self.homo = HomographyEstimator(template_norm, ema=PITCH_EMA_FACTOR)
        self._minimap_base = cv2.imread(PITCH_IMG_PATH)
        assert self._minimap_base is not None, "Can't Load minimap"
        self._minimap_size = (MAP_WIDTH, MAP_HEIGHT)
        self._minimap = cv2.resize(self._minimap_base, self._minimap_size, interpolation=cv2.INTER_LINEAR)

        self._prev_teamnum: Dict[int, Tuple[str, int]] = {}

        fps = video_info.fps or 25
        self.pos_logger = PositionsLogger(
            out_dir=self.cfg.frames_dir,
            fps=fps,
            minimap_size=self._minimap_size,
            start_frame=5,
            min_stable_frames=QF_MIN_STABLE_FRAMES,
            max_delta01=QF_MAX_DELTA01
        )

        self.ann_logger = AnnotationLogger(
            out_dir=self.cfg.frames_dir,
            fps=fps,
        )
        self.pitch_kp_logger = PitchKPLogger(
            out_dir=self.cfg.frames_dir,
            fps=fps,
        )

        self.traj_pitch: Dict[str, List[np.ndarray]] = {}
        self._last_seen_tid: Dict[int, int] = {}
        self._reappear_lock_frames = 12

        self.classifier = TeamClassifier(extractor, team_model)
        fps = video_info.fps or 25
        self.delay_ms = max(1, int(1000 / fps))
        hold_frames = max(1, int(self.cfg.BASE_HOLD_SEC * fps))
        self.stab = Stabilizer(self.cfg.MARGIN_MIN, hold_frames, self.cfg.PROX_FACTOR)

        self.STRONG_COLOR_MARGIN = TRACK_STRONG_COLOR_MARGIN   # warunek szybkiej zmiany drużyny
        self.WEAK_COLOR_PENALTY  = TRACK_WEAK_COLOR_PENALTY    # słaby kolor -> dłuższe przytrzymanei decyzji

        os.makedirs(os.path.dirname(cfg.output_path), exist_ok=True)
        os.makedirs(cfg.frames_dir, exist_ok=True)

    def _calc_neighbors(self, detections, proposals):
        close_neighbors = [False] * len(detections)
        centers = []
        for i in range(len(detections)):
            xyxy = detections.xyxy[i]
            centers.append((0.5*(xyxy[0]+xyxy[2]), 0.5*(xyxy[1]+xyxy[3])))
        for i in range(len(detections)):
            if not proposals[i] or proposals[i]['team'] is None:
                continue
            xi1, yi1, xi2, yi2 = map(float, detections.xyxy[i])
            thr = 0.6 * min(xi2-xi1, yi2-yi1)
            ci = centers[i]
            for j in range(len(detections)):
                if i == j or not proposals[j] or proposals[j]['team'] is None:
                    continue
                cj = centers[j]
                dist = np.hypot(ci[0]-cj[0], ci[1]-cj[1])
                if dist <= thr:
                    ti = proposals[i]['team']; tj = proposals[j]['team']
                    ti_ab = 'TEAM A' if 'TEAM A' in (ti or '') else ('TEAM B' if 'TEAM B' in (ti or '') else ti)
                    tj_ab = 'TEAM A' if 'TEAM A' in (tj or '') else ('TEAM B' if 'TEAM B' in (tj or '') else tj)
                    if ti_ab != tj_ab:
                        close_neighbors[i] = True
        return close_neighbors

    def _render_minimap(self, pts_by_id: dict, colors_by_id: dict):
        if not self.show_minimap:
            return
        mm = self._minimap.copy()
        h, w = mm.shape[:2]
        for pid, col in colors_by_id.items():
            trail = pts_by_id.get(pid)
            if not trail:
                continue
            x01, y01 = trail[-1]
            px = int(np.clip(x01, 0, 1) * (w - 1))
            py = int(np.clip(y01, 0, 1) * (h - 1))
            cv2.circle(mm, (px, py), 5, col, -1, lineType=cv2.LINE_AA)
        cv2.imshow("MiniMap", mm)


    # [REID-DEBUG] Rysowanie minimapy ze strefami przewidywanych pozycji zawodników
    def _render_minimap_with_zones(self, pts_by_id: dict, colors_by_id: dict, zones: list):
        if not self.show_minimap:
            return
        mm = self._minimap.copy()
        h, w = mm.shape[:2]

        # 1) rysowanie stref ReID (debug)
        overlay = mm.copy()
        for z in (zones or []):
            team = z.get("team")
            number = z.get("number")
            role = z.get("role")
            c01 = z.get("center01")
            rad01 = float(z.get("radius01", 0.0))

            if c01 is None or not np.isfinite(c01).all():
                continue

            x01, y01 = float(c01[0]), float(c01[1])
            if not (0.0 <= x01 <= 1.0 and 0.0 <= y01 <= 1.0):
                continue

            col_fill = (0, 0, 255)
            col_edge = (0, 0, 255)

            px = int(np.clip(x01, 0, 1) * (w - 1))
            py = int(np.clip(y01, 0, 1) * (h - 1))
            rad_px = int(rad01 * min(w, h))

            cv2.circle(overlay, (px, py), max(8, rad_px), col_fill, -1, lineType=cv2.LINE_AA)
            cv2.circle(overlay, (px, py), max(8, rad_px), col_edge, 3, lineType=cv2.LINE_AA)
            cv2.drawMarker(overlay, (px, py), (255, 255, 255),
                           markerType=cv2.MARKER_CROSS, markerSize=10,
                           thickness=2, line_type=cv2.LINE_AA)

            tag = f"{'#1' if role == 'GK' and number == 1 else '#' + str(number)}"
            cv2.putText(overlay, tag, (px + 10, py - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(overlay, tag, (px + 10, py - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        mm = cv2.addWeighted(overlay, 0.35, mm, 0.65, 0.0)

        for pid, col in colors_by_id.items():
            trail = pts_by_id.get(pid)
            if not trail:
                continue
            x01, y01 = trail[-1]
            px = int(np.clip(x01, 0, 1) * (w - 1))
            py = int(np.clip(y01, 0, 1) * (h - 1))
            cv2.circle(mm, (px, py), 5, col, -1, lineType=cv2.LINE_AA)

        cv2.imshow("MiniMap", mm)

    def _bbox_center(self, xyxy: Tuple[float, float, float, float]) -> Tuple[float, float]:
        x1, y1, x2, y2 = map(float, xyxy)
        return (0.5 * (x1 + x2), 0.5 * (y1 + y2))

    def _to_pitch01(self, xyxy: Tuple[float, float, float, float]) -> Optional[Tuple[float, float]]:
        if self.homo is None or not self.homo.is_ready():
            return None
        cx, cy = self._bbox_center(xyxy)
        pt = np.array([[cx, cy]], dtype=np.float32)
        out = self.homo.image_to_pitch01(pt)
        if out is None or not np.isfinite(out).all():
            return None
        x01, y01 = float(out[0, 0]), float(out[0, 1])
        if not (0.0 <= x01 <= 1.0 and 0.0 <= y01 <= 1.0):
            return None
        return (x01, y01)

    def _to_pitch01_foot(self, xyxy: Tuple[float, float, float, float]) -> Optional[Tuple[float, float]]:
        if self.homo is None or not self.homo.is_ready():
            return None
        x1, y1, x2, y2 = map(float, xyxy)
        foot = np.array([[0.5 * (x1 + x2), y2]], dtype=np.float32)
        out = self.homo.image_to_pitch01(foot)
        if out is None or not np.isfinite(out).all():
            return None
        x01, y01 = float(out[0, 0]), float(out[0, 1])
        if not (0.0 <= x01 <= 1.0 and 0.0 <= y01 <= 1.0):
            return None
        return (x01, y01)

    def _ensure_preview_window(self):
        if not self.show_preview:
            return
        if self._preview_window_created:
            return

        cv2.namedWindow(self._preview_window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self._preview_window_name, 1280, 720)
        self._preview_window_created = True

    def set_preview(self, enabled: bool):
        self.show_preview = bool(enabled)

    def set_minimap(self, enabled: bool):
        self.show_minimap = bool(enabled)

    def request_stop(self):
        self._stop_requested = True

    def run(self, progress_cb=None, frame_cb=None):
        window_name = self._preview_window_name

        try:
            tracker = sv.ByteTrack()
        except Exception:
            tracker = None

        frame_idx = 0
        last_t = time.time()
        ema_fps = None

        total_frames = int(getattr(self.video_info, "total_frames", 0) or 0)

        with sv.VideoSink(target_path=self.cfg.output_path, video_info=self.video_info) as sink:
            t_prev_yolo = time.perf_counter()
            for result in self.yolo.predict_video_stream(self.cfg.video_path):
                t_frame_start = time.perf_counter()

                t_yolo_done = time.perf_counter()
                self._perf_stats["yolo_players"] += (t_yolo_done - t_prev_yolo)

                frame_idx += 1
                frame = result.orig_img

                if self.show_preview and not self._prev_show_preview:
                    self._ensure_preview_window()
                elif not self.show_preview and self._prev_show_preview:
                    if self._preview_window_created:
                        try:
                            cv2.destroyWindow(self._preview_window_name)
                        except Exception:
                            pass
                        self._preview_window_created = False
                self._prev_show_preview = self.show_preview

                # --- Minimap window ---
                if not self.show_minimap and self._prev_show_minimap:
                    try:
                        cv2.destroyWindow("MiniMap")
                    except Exception:
                        pass
                self._prev_show_minimap = self.show_minimap
                if total_frames > 0:
                    if progress_cb is not None:
                        pct = int(frame_idx * 100 / total_frames)
                        if pct > 100:
                            pct = 100
                        progress_cb(pct)

                    if frame_cb is not None:
                        if (frame_idx % 5 == 0) or (frame_idx == total_frames):
                            frame_cb(frame_idx, total_frames)

                # 1) Keypoints + homography + pomiar
                t0_pk = time.perf_counter()

                pts_dict, conf_dict = self.pitch_kp.infer_keypoints(frame)
                self.homo.update(pts_dict)
                self.pitch_kp_logger.log(frame_idx, pts_dict, conf_dict)

                t1_pk = time.perf_counter()
                self._perf_stats["pitch_kp"] += (t1_pk - t0_pk)

                # START POMIARU GŁÓWNEJ LOGIKI CPU
                t_logic_start = time.perf_counter()

                # 2) Detections + tracker
                detections = sv.Detections.from_ultralytics(result)
                if tracker is not None and len(detections) > 0:
                    detections = tracker.update_with_detections(detections)

                names = np.array([self.yolo.model.model.names[int(cid)].lower() for cid in detections.class_id.astype(int)])
                label_texts: List[Optional[str]] = [None] * len(detections)
                label_colors: List[Optional[tuple]] = [None] * len(detections)
                triangle_colors: List[Optional[tuple]] = [None] * len(detections)
                tracker_ids = getattr(detections, 'tracker_id', None)
                if tracker_ids is None:
                    tracker_ids = np.arange(1, len(detections) + 1)

                # 3) Team proposals
                proposals = []
                for i in range(len(detections)):
                    cname = names[i]
                    if cname not in ('player', 'goalkeeper', 'referee'):
                        proposals.append(None)
                        continue
                    try:
                        obj_id = int(tracker_ids[i])
                    except Exception:
                        obj_id = i + 1
                    xyxy = tuple(map(float, detections.xyxy[i]))
                    team_text, team_color, dA, dB = self.classifier.classify(frame, xyxy, cname)
                    if team_text is None:
                        proposals.append(
                            {'id': obj_id, 'cls': cname, 'team': None, 'color': None, 'dA': None, 'dB': None})
                    else:
                        margin = None if (dA is None or dB is None) else abs(dA - dB)
                        proposals.append(
                            {'id': obj_id, 'cls': cname, 'team': team_text, 'color': team_color, 'dA': dA, 'dB': dB,
                             'margin': margin})

                # 4) Limits for referee and goalkeepers
                confs = getattr(detections, "confidence", None)
                if confs is None:
                    confs = np.ones(len(detections), dtype=np.float32)

                mask_keep = np.ones(len(detections), dtype=bool)

                ref_idxs = [i for i, p in enumerate(proposals) if p and p['cls'] == 'referee' and p.get('team') == 'referee']
                if len(ref_idxs) > 0:
                    H, W = frame.shape[:2]
                    ref_scores = []
                    for i in ref_idxs:
                        xyxy = tuple(map(float, detections.xyxy[i]))
                        p01_foot = self._to_pitch01_foot(xyxy)

                        cx, cy = self._bbox_center(xyxy)
                        x1, y1, x2, y2 = map(float, xyxy)

                        if p01_foot is not None:
                            if not is_in_central_band(p01_foot):
                                mask_keep[i] = False; continue
                        else:
                            if not (0.25 * W <= cx <= 0.75 * W):
                                mask_keep[i] = False; continue

                        if p01_foot is not None:
                            if is_near_touchline(p01_foot, margin_x=0.15):
                                mask_keep[i] = False; continue
                        else:
                            if (cx <= 0.15 * W) or (cx >= 0.85 * W):
                                mask_keep[i] = False; continue

                        if (y2 >= 0.90 * H) or (y1 <= 0.10 * H):
                            mask_keep[i] = False; continue

                        center_bonus = 1.0 - min(1.0, abs(cx - 0.5 * W) / (0.5 * W))
                        score = float(confs[i]) + 0.6 * center_bonus + 0.5
                        ref_scores.append((score, i))

                    if len(ref_scores) > 0:
                        keep_prev = set()
                        if getattr(detections, 'tracker_id', None) is not None and len(self.referee_ids) > 0:
                            for i in ref_idxs:
                                try:
                                    tid_i = int(detections.tracker_id[i])
                                    if tid_i in self.referee_ids and mask_keep[i]:
                                        keep_prev.add(i)
                                except Exception:
                                    pass

                        ref_scores.sort(reverse=True, key=lambda t: t[0])
                        chosen = set(keep_prev)
                        for _, i in ref_scores:
                            if len(chosen) >= 3:
                                break
                            if mask_keep[i] and i not in chosen:
                                chosen.add(i)

                        for i in ref_idxs:
                            if i not in chosen:
                                mask_keep[i] = False

                        if getattr(detections, 'tracker_id', None) is not None:
                            chosen_ids = set()
                            for i in chosen:
                                try:
                                    chosen_ids.add(int(detections.tracker_id[i]))
                                except Exception:
                                    pass
                            self.referee_ids = chosen_ids

                # GK: 1 na drużyne, z premią w polu karnym
                gk_idxs = [i for i, p in enumerate(proposals) if p and p['cls'] == 'goalkeeper']
                if len(gk_idxs) > 0:
                    buckets = {"TEAM A": [], "TEAM B": []}  # (score, i)
                    for i in gk_idxs:
                        xyxy = tuple(map(float, detections.xyxy[i]))
                        p01 = self._to_pitch01(xyxy)
                        in_pen = penalty_side(p01) if p01 is not None else None
                        pen_bonus = 0.6 if in_pen is not None else -0.2

                        base = float(confs[i])
                        age_bonus = 0.0
                        score = base + pen_bonus + age_bonus

                        team = proposals[i]['team']
                        if isinstance(team, str) and team.startswith("TEAM A"):
                            buckets["TEAM A"].append((score, i))
                        elif isinstance(team, str) and team.startswith("TEAM B"):
                            buckets["TEAM B"].append((score, i))

                    for tkey in ("TEAM A", "TEAM B"):
                        if len(buckets[tkey]) > 0:
                            buckets[tkey].sort(reverse=True, key=lambda t: t[0])
                            _, best_i = buckets[tkey][0]
                            for _, i in buckets[tkey][1:]:
                                mask_keep[i] = False
                            if getattr(detections, 'tracker_id', None) is not None:
                                self.gk_ids[tkey] = int(detections.tracker_id[best_i])

                if not np.all(mask_keep):
                    detections = detections[mask_keep]
                    proposals = [p for p, keep in zip(proposals, mask_keep) if keep]
                    names = names[mask_keep]
                    if getattr(detections, 'tracker_id', None) is not None:
                        tracker_ids = detections.tracker_id
                    else:
                        tracker_ids = np.arange(1, len(detections) + 1)

                # 5) Stabilization of labels/teams
                close_neighbors = self._calc_neighbors(detections, proposals)
                for i in range(len(detections)):
                    cname = names[i]
                    if cname not in ('player', 'goalkeeper', 'referee'):
                        continue
                    try:
                        obj_id = int(tracker_ids[i])
                    except Exception:
                        obj_id = i + 1
                    st = self.stab.get(obj_id)
                    prop = proposals[i]

                    # [REF-GUARD] Stick to referee
                    if obj_id in self.referee_ids and prop is not None and prop.get('team') == 'referee':
                        st.team = 'referee'
                        st.color = self.classifier.REF_COLOR
                        st.pending_team = None
                        st.pending_since_frame = None
                        st.last_confirm_frame = frame_idx
                        label_texts[i] = f'referee #{obj_id}'
                        label_colors[i] = st.color
                        triangle_colors[i] = st.color
                        continue

                    if prop is None or prop['team'] is None:
                        if st.team is not None:
                            label_texts[i] = f'{st.team} #{obj_id}'
                            label_colors[i] = st.color; triangle_colors[i] = st.color
                        else:
                            label_texts[i] = f'{cname} #{obj_id}'
                            label_colors[i] = (255, 255, 255); triangle_colors[i] = (255, 255, 255)
                        continue

                    proposed_team = prop['team']; proposed_color = prop['color']; margin = prop.get('margin')

                    if st.team is None:
                        if margin is None or margin >= (0.5 * self.stab.margin_min):
                            st.team = proposed_team; st.color = proposed_color
                            st.last_confirm_frame = frame_idx
                            st.pending_team = None; st.pending_since_frame = None
                            label_texts[i] = f'{st.team} #{obj_id}'
                            label_colors[i] = st.color; triangle_colors[i] = st.color
                        else:
                            st.pending_team = proposed_team; st.pending_color = proposed_color
                            st.pending_since_frame = frame_idx if st.pending_since_frame is None else st.pending_since_frame
                            label_texts[i] = f'{proposed_team}? #{obj_id}'
                            label_colors[i] = proposed_color; triangle_colors[i] = proposed_color
                        continue

                    if proposed_team == st.team:
                        st.color = proposed_color; st.last_confirm_frame = frame_idx
                        st.pending_team = None; st.pending_since_frame = None
                        label_texts[i] = f'{st.team} #{obj_id}'
                        label_colors[i] = st.color; triangle_colors[i] = st.color
                        continue

                    # --- [APPEARANCE-GATE] Silny sygnał koloru - szybka zmiana drużyny
                    strong_color = (margin is not None and margin >= self.STRONG_COLOR_MARGIN)
                    # [REF-GUARD] Brak szybkich przełączeń z roli sędziego
                    if ((st.team == 'referee') or (obj_id in self.referee_ids)) and (prop is None or prop.get('team') == 'referee'):
                        strong_color = False

                    if strong_color:
                        # debug - strong flip
                        # print(f"[appearance] STRONG FLIP: tid={obj_id} margin={margin:.3f} "
                        #       f"{st.team} -> {proposed_team} @frame {frame_idx}")
                        st.team = proposed_team
                        st.color = proposed_color
                        st.last_confirm_frame = frame_idx
                        st.pending_team = None
                        st.pending_since_frame = None
                        label_texts[i] = f'{st.team} #{obj_id}'
                        label_colors[i] = st.color; triangle_colors[i] = st.color
                        continue

                    if margin is not None and margin < self.stab.margin_min:
                        st.pending_team = proposed_team; st.pending_color = proposed_color
                        st.pending_since_frame = frame_idx if st.pending_since_frame is None else st.pending_since_frame
                        label_texts[i] = f'{st.team} #{obj_id}'
                        label_colors[i] = st.color; triangle_colors[i] = st.color
                        continue

                    # --- Debounce (HOLD) - opóźnienie zmiany drużyny  ---
                    hold_frames = int(self.stab.hold_frames_base * (self.stab.prox_factor if close_neighbors[i] else 1.0))

                    if st.pending_team != proposed_team:
                        st.pending_team = proposed_team; st.pending_color = proposed_color; st.pending_since_frame = frame_idx

                    elapsed = frame_idx - (st.pending_since_frame or frame_idx)
                    required = max(hold_frames, self.stab.min_switch_frames)
                    # --- [APPEARANCE-GATE] Słaby kolor - dłuższe podtrzymanie starej drużyny ---
                    required = int(required * self.WEAK_COLOR_PENALTY)
                    # debug - weak penalty
                    # print(f"[appearance] weak penalty: tid={obj_id} margin={margin if margin is not None else -1:.3f} "
                    #       f"required={required} elapsed={elapsed} prox={close_neighbors[i]} @frame {frame_idx}")

                    if elapsed >= required:
                        st.team = st.pending_team; st.color = st.pending_color; st.last_confirm_frame = frame_idx
                        st.pending_team = None; st.pending_since_frame = None
                        label_texts[i] = f'{st.team} #{obj_id}'
                        label_colors[i] = st.color; triangle_colors[i] = st.color
                    else:
                        label_texts[i] = f'{st.team} #{obj_id}'
                        label_colors[i] = st.color; triangle_colors[i] = st.color

                # ====== LIMIT: maksymalnie 10 zawodników na drużynę (bez bramkarza) ======
                hidden_idxs = set()
                if len(detections) > 0:
                    H, W = frame.shape[:2]
                    buckets = {"TEAM A": [], "TEAM B": []}  # listy par: (priorytet, indeks detekcji)

                    for i in range(len(detections)):
                        cname = names[i]
                        if cname != 'player':
                            continue

                        # [REF-GUARD]
                        try:
                            if int(tracker_ids[i]) in self.referee_ids:
                                continue
                        except Exception:
                            pass

                        # Wybór drużynny
                        st_i = self.stab.get(int(tracker_ids[i]))
                        team_key = None
                        if st_i and st_i.team and ('TEAM A' in st_i.team or 'TEAM B' in st_i.team):
                            team_key = 'TEAM A' if 'TEAM A' in st_i.team else 'TEAM B'
                        else:
                            if proposals[i] and proposals[i]['team']:
                                t = proposals[i]['team']
                                team_key = 'TEAM A' if 'TEAM A' in t else ('TEAM B' if 'TEAM B' in t else None)

                        if team_key is None:
                            continue

                        conf = float(getattr(detections, "confidence", np.ones(len(detections)))[i])
                        x1, y1, x2, y2 = map(float, detections.xyxy[i])
                        cx = 0.5 * (x1 + x2)
                        center_bonus = 1.0 - min(1.0, abs(cx - 0.5 * W) / (0.5 * W))
                        last_conf = (st_i.last_confirm_frame or 0) if st_i else 0
                        recency = 1.0 / (1.0 + max(0, frame_idx - last_conf))
                        central = 0.0
                        if self.homo.is_ready():
                            p01 = self._to_pitch01((x1, y1, x2, y2))
                            if p01 is not None:
                                central = max(0.0, 1.0 - abs(p01[0] - 0.5) * 2.0)

                        priority = (0.6 * conf) + (0.3 * center_bonus) + (0.1 * recency) + (0.1 * central)
                        buckets[team_key].append((priority, i))

                    # Wybierz 10 najwyższych priorytetow na drużynę
                    for team_key, arr in buckets.items():
                        if len(arr) <= 10:
                            continue
                        arr.sort(reverse=True, key=lambda t: t[0])
                        keep_set = set(idx for _, idx in arr[:10])
                        for _, idx in arr[10:]:
                            hidden_idxs.add(idx)

                    if hidden_idxs:
                        for i in hidden_idxs:
                            label_texts[i] = None
                            triangle_colors[i] = None
                            label_colors[i] = None

                # === aktualizacja etykiet (dodanie numerów 1–11)  ===
                tid_to_teamnum = {}
                reid_zones = []  # [REID-DEBUG]
                if self.homo.is_ready() and len(detections) > 0:
                    tid_list, pos_list, team_list, role_list = [], [], [], []
                    for i in range(len(detections)):
                        cname = names[i]
                        if cname not in ('player', 'goalkeeper'):
                            continue
                        try:
                            tid_i = int(tracker_ids[i])
                        except Exception:
                            tid_i = i + 1

                        # [REF-GUARD]
                        if tid_i in self.referee_ids:
                            self._last_seen_tid[tid_i] = frame_idx
                            continue

                        # Pozycja
                        x1, y1, x2, y2 = map(float, detections.xyxy[i])
                        foot = np.array([[0.5 * (x1 + x2), y2]], dtype=np.float32)
                        p01 = self.homo.image_to_pitch01(foot)
                        pt = p01[0] if p01 is not None else None

                        # drużyna – stabilizator - propozycja zmiany
                        st_i = self.stab.get(tid_i)
                        tkey = None
                        if st_i and st_i.team and ('TEAM A' in st_i.team or 'TEAM B' in st_i.team):
                            tkey = 'TEAM A' if 'TEAM A' in st_i.team else 'TEAM B'
                        elif proposals[i] and proposals[i]['team']:
                            t = proposals[i]['team']
                            tkey = 'TEAM A' if 'TEAM A' in t else ('TEAM B' if 'TEAM B' in t else None)

                        role = 'GK' if cname == 'goalkeeper' else 'player'

                        # --- Ponowne pojawienie się ---
                        last_seen_prev = self._last_seen_tid.get(tid_i, None)
                        is_reappear = (last_seen_prev is not None) and ((frame_idx - last_seen_prev) > 1)
                        if is_reappear:
                            if st_i and st_i.team and ('TEAM A' in st_i.team or 'TEAM B' in st_i.team):
                                tkey = 'TEAM A' if 'TEAM A' in st_i.team else 'TEAM B'
                            else:
                                self._last_seen_tid[tid_i] = frame_idx
                                continue

                        tid_list.append(tid_i)
                        pos_list.append(np.array(pt, np.float32) if pt is not None else None)
                        team_list.append(tkey)
                        role_list.append(role)
                        self._last_seen_tid[tid_i] = frame_idx

                    tid_to_teamnum = self.squad.update(tid_list, pos_list, team_list, role_list, frame_idx)

                    # [REID-DEBUG] pobierz strefy ReID z managera
                    try:
                        reid_zones = self.squad.get_reid_zones()
                    except Exception:
                        reid_zones = []

                # --- KONIEC GŁÓWNEJ LOGIKI CPU ---
                t_logic_end = time.perf_counter()
                self._perf_stats["cpu_logic"] += (t_logic_end - t_logic_start)

                # --- START POMIARU LOGOWANIA / I/O ---
                t_log_start = time.perf_counter()

                # === logger pozycji do csv ===
                if len(detections) > 0 and self.homo.is_ready():
                    try:
                        self.pos_logger.log_from_detections(
                            frame_idx=frame_idx,
                            detections=detections,
                            names=names,
                            tracker_ids=tracker_ids,
                            tid_to_teamnum=tid_to_teamnum,
                            homography=self.homo,
                            stabilizer=self.stab,
                            referee_ids=self.referee_ids
                        )
                    except Exception as e:
                        print("positions_logger warn:", e)

                # Zmiena numerów
                for i in range(len(detections)):
                    cname = names[i]
                    if cname not in ('player', 'goalkeeper'):
                        continue
                    try:
                        tid_i = int(tracker_ids[i])
                    except Exception:
                        tid_i = i + 1

                    if tid_i in tid_to_teamnum:
                        team_tag, num = tid_to_teamnum[tid_i]
                        tag = f'#{num}'
                        base = label_texts[i] or f'{cname} #{tid_i}'
                        if '#' in base:
                            base = base.split('#')[0].strip() + f' {tag}'
                        else:
                            base = base + f' {tag}'
                        label_texts[i] = base

                # === Pozycje zawodników na mapie ===
                if self.homo.is_ready():
                    colors_by_id: Dict[str, tuple] = {}
                    for i in range(len(detections)):
                        cname = names[i]
                        if cname not in ('player', 'goalkeeper'):
                            continue

                        try:
                            tid_i = int(tracker_ids[i])
                        except Exception:
                            tid_i = i + 1

                        if tid_i in tid_to_teamnum:
                            team_tag, num = tid_to_teamnum[tid_i]
                            traj_key = f'{team_tag}:{num}'
                        else:
                            continue

                        # Position taken from player feet
                        x1, y1, x2, y2 = map(float, detections.xyxy[i])
                        foot = np.array([[0.5 * (x1 + x2), y2]], dtype=np.float32)
                        p01 = self.homo.image_to_pitch01(foot)
                        if p01 is not None:
                            self.traj_pitch.setdefault(traj_key, []).append(p01[0])

                        # Color if team is known
                        st_i = self.stab.get(tid_i)
                        if st_i and st_i.team and ('TEAM A' in st_i.team or 'TEAM B' in st_i.team):
                            colors_by_id[traj_key] = st_i.color


                    # [REID-DEBUG] render z widocznymi strefami ReID
                    self._render_minimap_with_zones(self.traj_pitch, colors_by_id, reid_zones)

                # [REID-DEBUG] log: przydziały i duplikaty
                # if tid_to_teamnum:
                #     for tid_i, teamnum in tid_to_teamnum.items():
                #         prev = self._prev_teamnum.get(tid_i)
                #         if prev != teamnum:
                #             print(f"[squad] assign: tid={tid_i} {prev} -> {teamnum} @frame {frame_idx}")
                #
                #     rev: Dict[Tuple[str,int], List[int]] = {}
                #     for tid_i, (tkey, num) in tid_to_teamnum.items():
                #         rev.setdefault((tkey, num), []).append(tid_i)
                #     for (tkey, num), tids in rev.items():
                #         if len(tids) > 1:
                #             print(f"[squad] DUP team={tkey} #{num} tids={tids} @frame {frame_idx}")
                #
                #     self._prev_teamnum = dict(tid_to_teamnum)

                # CSV logger
                try:
                    self.ann_logger.log_frame(
                        frame_idx=frame_idx,
                        detections=detections,
                        names=names,
                        tracker_ids=tracker_ids,
                        label_texts=label_texts,
                        label_colors_bgr=label_colors,
                        triangle_colors_bgr=triangle_colors,
                    )
                except Exception as e:
                    print(f"[ann_logger] błąd logowania @frame {frame_idx}: {e}")

                # --- KONIEC LOGOWANIA / I/O ---
                t_log_end = time.perf_counter()
                self._perf_stats["logging"] += (t_log_end - t_log_start)

                # 6)Render + zapis
                rendered = annotate_people_custom_labels(
                    frame.copy(), detections, self.yolo.model.model.names, label_texts, label_colors, triangle_colors_bgr=triangle_colors
                )

                now = time.time()
                inst_fps = 1.0 / max(1e-6, (now - last_t))
                ema_fps = inst_fps if ema_fps is None else (0.9 * ema_fps + 0.1 * inst_fps)
                last_t = now
                info_text = f'frame: {frame_idx}  |  FPS: {ema_fps:5.1f}'
                cv2.putText(rendered, info_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 3, cv2.LINE_AA)
                cv2.putText(rendered, info_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)

                sink.write_frame(rendered)
                t_prev_yolo = time.perf_counter()
                # --- AKTUALIZACJA STATYSTYK PERF ---
                self._perf_stats["frames"] += 1
                fcnt = self._perf_stats["frames"]

                if fcnt % 100 == 0:  # co ile klatek log szybkości
                    avg_yolo_ms = (self._perf_stats["yolo_players"] / fcnt) * 1000.0
                    avg_pk_ms = (self._perf_stats["pitch_kp"] / fcnt) * 1000.0
                    avg_cpu_ms = (self._perf_stats["cpu_logic"] / fcnt) * 1000.0
                    avg_log_ms = (self._perf_stats["logging"] / fcnt) * 1000.0
                    total_ms = avg_yolo_ms + avg_pk_ms + avg_cpu_ms + avg_log_ms
                    fps_est = 1000.0 / max(1e-6, total_ms)

                    print("\n[PERF] Po", fcnt, "klatkach:")
                    print(f"  YOLO (players): {avg_yolo_ms:6.2f} ms/klatka")
                    print(f"  PitchKP+H      : {avg_pk_ms:6.2f} ms/klatka")
                    print(f"  CPU logic      : {avg_cpu_ms:6.2f} ms/klatka")
                    print(f"  Logging / I/O  : {avg_log_ms:6.2f} ms/klatka")
                    print(f"  SUMA ≈         : {total_ms:6.2f} ms/klatka  (~{fps_est:5.1f} FPS offline)")

                #--- Dla przycisku stop analizy ---
                self._last_frame_idx = frame_idx
                if self._stop_requested:
                    break

                # --- Podgląd yolo  ---
                if self.show_preview:
                    self._ensure_preview_window()
                    cv2.imshow(self._preview_window_name, rendered)

                # --- Jedna pętla dla wszystkich okien ---
                key = -1
                if self.show_preview or self.show_minimap:
                    key = cv2.waitKey(self.delay_ms) & 0xFF

                if self.show_preview and key != -1:
                    if key in (ord('q'), 27):
                        break
                    elif key == ord(' '):
                        cv2.waitKey(0)
                    elif key == ord('s'):
                        out_img = os.path.join(self.cfg.frames_dir, f'frame_{frame_idx:06d}.png')
                        cv2.imwrite(out_img, rendered)
                        print(f'Saved: {out_img}')

                t_frame_end = time.perf_counter()
                self._perf_stats["frame_total"] += (t_frame_end - t_frame_start)
        # --- Zamknięcie loggera ---
        try:
            self.pos_logger.close()
            print(f"Position Saved to: {self.pos_logger.csv_path}")
        except Exception as e:
            print("!Can't close positions_logger!", e)

        try:
            self.ann_logger.close()
            print(f"Annotations saved to: {self.ann_logger.csv_path}")
        except Exception as e:
            print("!can't close annotation_logger!", e)

        try:
            self.pitch_kp_logger.close()
            print(f"Keypoints saved to: {self.pitch_kp_logger.csv_path}")
        except Exception as e:
            print("!Can't close pitch_kp_logger!", e)

        # --- FINALNE PODSUMOWANIE PERF ---
        fcnt = max(1, self._perf_stats.get("frames", 1))

        avg_yolo_ms = (self._perf_stats["yolo_players"] / fcnt) * 1000.0
        avg_pk_ms = (self._perf_stats["pitch_kp"] / fcnt) * 1000.0
        avg_cpu_ms = (self._perf_stats["cpu_logic"] / fcnt) * 1000.0
        avg_log_ms = (self._perf_stats["logging"] / fcnt) * 1000.0
        total_ms = avg_yolo_ms + avg_pk_ms + avg_cpu_ms + avg_log_ms

        # pełny czas klatki (YOLO + reszta + I/O + GUI)
        avg_frame_ms = (self._perf_stats["frame_total"] / fcnt) * 1000.0
        fps_real = 1000.0 / max(1e-6, avg_frame_ms)

        print("\n=== FINAL PERF SUMMARY (pipeline) ===")
        print(f"  Klatek          : {fcnt}")
        print(f"  YOLO (players)  : {avg_yolo_ms:6.2f} ms/klatka")
        print(f"  PitchKP+H       : {avg_pk_ms:6.2f} ms/klatka")
        print(f"  CPU logic       : {avg_cpu_ms:6.2f} ms/klatka")
        print(f"  Logging / I/O   : {avg_log_ms:6.2f} ms/klatka")
        print(f"  SUMA (bez GUI + sink) ≈ : {total_ms:6.2f} ms/klatka")
        print(f"  REAL frame time (FULL) : {avg_frame_ms:6.2f} ms/klatka  (~{fps_real:5.1f} FPS end-to-end)")

        # --- Podsumowanie YOLO z YoloRunner ---
        try:
            if hasattr(self.yolo, "print_perf_summary"):
                print("\n=== YOLO (players) PERF SUMMARY ===")
                self.yolo.print_perf_summary()
        except Exception:
            pass



        cv2.destroyAllWindows()
        print(f'Video saved: {self.cfg.output_path}')
        return int(self._last_frame_idx)

