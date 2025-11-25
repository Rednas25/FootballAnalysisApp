import numpy as np
from core.tracking.colors_utils import team_color_from_proto, emd_lite
from core.config import REF_TEAM_OVERRULE_FACTOR

class TeamClassifier:
    def __init__(self, extractor, team_model: dict):
        self.extractor = extractor
        self.team_model = team_model

        self.TEAM_A_COLOR = team_color_from_proto(team_model.get("teamA_player", {}))
        self.TEAM_B_COLOR = team_color_from_proto(team_model.get("teamB_player", {}))
        self.GK_A_COLOR   = team_color_from_proto(team_model.get("teamA_goalkeeper", {})) or self.TEAM_A_COLOR
        self.GK_B_COLOR   = team_color_from_proto(team_model.get("teamB_goalkeeper", {})) or self.TEAM_B_COLOR
        self.REF_COLOR    = team_color_from_proto(team_model.get("referee", {}))
        if self.REF_COLOR == (255, 255, 255):
            self.REF_COLOR = (60, 60, 60)

    def _get_proto(self, key):
        p = self.team_model.get(key, None)
        if p is None:
            return np.empty((0,2), np.float32), np.empty((0,), np.float32)
        return p.get("centers_ab", np.empty((0,2), np.float32)), p.get("weights", np.empty((0,), np.float32))

    def classify(self, frame_bgr, xyxy, cls_name_lower: str):
        """
        Zwraca:
            team_text: "TEAM A" / "TEAM B" / "TEAM A (GK)" / "TEAM B (GK)" / "referee" / None
            team_color: BGR
            dA, dB: odległości EMD do prototypów TEAM A / TEAM B (dla debug / marginesów)
        """
        # 1) Analiza koloru w boxie (dla wszystkich klas – też referee)
        analysis = self.extractor.analyze_box(frame_bgr, xyxy)
        centers, weights = self.extractor.extract_mixture_for_emd(
            analysis, reject_grass=True, top_m=4, cap_each=0.22, reweight_gamma=None
        )

        if centers.size == 0 or weights.size == 0:
            if cls_name_lower == "referee":
                return "referee", self.REF_COLOR, None, None
            return None, None, None, None

        # 2) Specjalny case: sędzia
        if cls_name_lower == "referee":
            c_ref, w_ref = self._get_proto("referee")
            cA, wA = self._get_proto("teamA_player")
            cB, wB = self._get_proto("teamB_player")

            has_ref = len(w_ref) > 0 and c_ref.size > 0

            if not has_ref:
                return "referee", self.REF_COLOR, None, None

            d_ref = emd_lite(centers, weights, c_ref, w_ref) if len(w_ref) else 1e9
            dA = emd_lite(centers, weights, cA, wA) if len(wA) else 1e9
            dB = emd_lite(centers, weights, cB, wB) if len(wB) else 1e9

            if dA <= dB:
                best_team = "TEAM A"
                best_team_color = self.TEAM_A_COLOR
                d_team = dA
            else:
                best_team = "TEAM B"
                best_team_color = self.TEAM_B_COLOR
                d_team = dB

            # Jeśli kolor drużyny jest wyraźnie lepszy niż kolor sędziego,
            # uznajemy że yolo sie pomyliło
            if d_team < d_ref * float(REF_TEAM_OVERRULE_FACTOR):
                return best_team, best_team_color, dA, dB

            return "referee", self.REF_COLOR, dA, dB

        if cls_name_lower == "goalkeeper":
            cA, wA = self._get_proto("teamA_goalkeeper")
            cB, wB = self._get_proto("teamB_goalkeeper")
            if len(wA) == 0:
                cA, wA = self._get_proto("teamA_player")
            if len(wB) == 0:
                cB, wB = self._get_proto("teamB_player")
            colorA, colorB = self.GK_A_COLOR, self.GK_B_COLOR
        else:
            cA, wA = self._get_proto("teamA_player")
            cB, wB = self._get_proto("teamB_player")
            colorA, colorB = self.TEAM_A_COLOR, self.TEAM_B_COLOR

        if len(wA) == 0 and len(wB) == 0:
            return None, None, None, None

        dA = emd_lite(centers, weights, cA, wA) if len(wA) else 1e9
        dB = emd_lite(centers, weights, cB, wB) if len(wB) else 1e9

        team = "TEAM A" if dA < dB else "TEAM B"
        color = colorA if dA < dB else colorB
        if cls_name_lower == "goalkeeper":
            team += " (GK)"
        return team, color, dA, dB
