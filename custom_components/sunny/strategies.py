"""Stratégies de pilotage des stores."""

import math
from abc import ABC, abstractmethod

try:
    from .solar_math import _ray_box_intersect
except ImportError:
    from solar_math import _ray_box_intersect


class BaseStrategy(ABC):
    """Classe de base pour une stratégie de pilotage."""

    name: str
    label: str = ""

    @abstractmethod
    def compute_position(self, data: dict) -> int:
        """Calcule la position désirée du store (0=fermé, 100=ouvert)."""


def _lit_at_cover_position(data: dict, cover_pos: float) -> float:
    """Calcule le pourcentage d'éclairement si le store est à cover_pos %.

    Utilise un masque d'ombre pré-calculé (ombres d'embrasure + obstacles 3D)
    et applique le modèle store (tilt / levée) par-dessus.
    """
    Hw = data.get("window_height", 1.0)
    W = data.get("window_width", 1.0)
    tilt_threshold = data.get("tilt_threshold", 5.0)
    slat_transmission = data.get("slat_transmission", 5.0)
    area = W * Hw
    if area <= 0:
        return 0.0

    if data.get("behind") or data.get("lit_pct", 0) == 0:
        return 0.0

    mask = _build_shadow_mask(data)
    if not mask:
        return 0.0

    nx = len(mask)
    nz = len(mask[0])
    cell_area = area / (nx * nz)

    # Position du bas du store (depuis le haut)
    if tilt_threshold <= 0 or tilt_threshold >= 100:
        y_cover = Hw * (1.0 - cover_pos / 100.0)
    else:
        effective_pos = (cover_pos - tilt_threshold) / (100.0 - tilt_threshold) * 100.0
        y_cover = Hw * (1.0 - effective_pos / 100.0)

    # Hauteur du store depuis le bas : Hw - y_cover
    store_bottom_from_bottom = Hw - y_cover

    lit_area = 0.0
    for ix in range(nx):
        for iz in range(nz):
            if not mask[ix][iz]:
                continue
            z_w = (iz + 0.5) * Hw / nz

            if tilt_threshold <= 0 or tilt_threshold >= 100:
                if z_w < store_bottom_from_bottom:
                    lit_area += cell_area
            elif cover_pos <= tilt_threshold:
                transmission = (cover_pos / tilt_threshold) * (slat_transmission / 100.0)
                lit_area += cell_area * transmission
            else:
                if z_w < store_bottom_from_bottom:
                    lit_area += cell_area
                else:
                    lit_area += cell_area * (slat_transmission / 100.0)

    return (lit_area / area * 100.0) if area > 0 else 0.0


def _build_shadow_mask(data: dict) -> list[list[bool]]:
    """Construit un masque booléen nx × nz : True = non ombré.

    Combine les ombres d'embrasure (d_lat, d_vert) et les obstacles 3D.
    """
    W = data.get("window_width", 1.0)
    Hw = data.get("window_height", 1.0)
    d_lat = data.get("d_lat", 0.0)
    d_vert = data.get("d_vert", 0.0)
    obstacles = data.get("obstacles", [])
    gamma = data.get("gamma", 0.0)
    h = data.get("solar_altitude", 0.0)

    R = 100
    nx = max(1, int(W * R))
    nz = max(1, int(Hw * R))

    g_rad = math.radians(gamma)
    h_rad = math.radians(h)
    dir_x = math.sin(g_rad) * math.cos(h_rad)
    dir_y = math.cos(g_rad) * math.cos(h_rad)
    dir_z = math.sin(h_rad)

    mask = [[False] * nz for _ in range(nx)]

    for ix in range(nx):
        x_w = (ix + 0.5) * W / nx
        for iz in range(nz):
            z_w = (iz + 0.5) * Hw / nz
            if x_w < d_lat or x_w > W - d_lat:
                continue
            if z_w > Hw - d_vert:
                continue
            blocked = False
            for obs in obstacles:
                if _ray_box_intersect(x_w, 0.0, z_w, dir_x, dir_y, dir_z, obs):
                    blocked = True
                    break
            if not blocked:
                mask[ix][iz] = True

    return mask


def _block_all_position(data: dict) -> int:
    """Trouve la position du store qui bloque tout soleil direct.

    Parcourt la grille de bas en haut et retourne la position où le bas
    du store couvre tous les points non ombrés.
    """
    if data.get("behind") or data.get("lit_pct", 0) == 0:
        return 100

    Hw = data.get("window_height", 1.0)
    mask = _build_shadow_mask(data)
    if not mask:
        return 100

    nx = len(mask)
    nz = len(mask[0])

    for iz in range(nz):
        z = (iz + 0.5) * Hw / nz
        if any(mask[ix][iz] for ix in range(nx)):
            pos = 100.0 * z / Hw
            return max(0, min(100, round(pos)))

    return 100


def search_cover_position(data: dict, target_pct: float) -> int:
    """Recherche binaire optimisée (5% + binaire) de la position du store
    qui donne au moins target_pct % d'ensoleillement. Retourne 0-100."""
    if data.get("behind") or data.get("lit_pct", 0) == 0:
        return 100

    # Étape 1 : balayage par pas de 5 %
    lo, hi = 100, 0
    found = False
    prev_lit = _lit_at_cover_position(data, 0)
    if prev_lit >= target_pct:
        return 0  # même tout fermé, assez de lumière (cas rare)

    for p in range(5, 101, 5):
        lit = _lit_at_cover_position(data, p)
        if prev_lit < target_pct <= lit:
            lo, hi = p - 5, p
            found = True
            break
        prev_lit = lit

    if not found:
        return 100 if _lit_at_cover_position(data, 100) >= target_pct else 0

    # Étape 2 : recherche binaire dans [lo, hi] pour trouver le minimum >= target_pct
    for _ in range(8):
        mid = (lo + hi) / 2.0
        lit = _lit_at_cover_position(data, mid)
        if lit >= target_pct:
            hi = mid
        else:
            lo = mid

    return min(100, max(0, round((lo + hi) / 2.0)))


# ---------------------------------------------------------------------------
# Stratégies
# ---------------------------------------------------------------------------


class BlockAllStrategy(BaseStrategy):
    """Bloque tout le soleil direct — été / canicule."""

    name = "block_all"
    label = "Bloquer tout soleil direct (été/canicule)"

    def compute_position(self, data: dict) -> int:
        return _block_all_position(data)


class WinterPassiveStrategy(BaseStrategy):
    """Chauffage solaire passif — hiver : ouvert si soleil, fermé sinon."""

    name = "winter_passive"
    label = "Chauffage passif hiver (soleil=ouvert, sinon=fermé)"

    def compute_position(self, data: dict) -> int:
        lit_pct = data.get("lit_pct", 0)
        if lit_pct > 0:
            return 100
        return 0


class ProportionalStrategy(BaseStrategy):
    """Proportionnel à l'ensoleillement : plus il y a de soleil, plus on ferme."""

    name = "proportional"
    label = "Proportionnel à l'ensoleillement"

    def compute_position(self, data: dict) -> int:
        lit_pct = data.get("lit_pct", 0)
        if lit_pct == 0:
            return 100
        pos = 100.0 - lit_pct
        return min(100, max(0, round(pos)))


class ThresholdStrategy(BaseStrategy):
    """Seuil simple : ferme au-dessus d'un seuil, ouvre en-dessous."""

    name = "threshold"
    label = "Seuil (ferme si ensoleillé, ouvre si ombre)"

    def compute_position(self, data: dict) -> int:
        high = data.get("strategy_high", 50.0)
        low = data.get("strategy_low", 20.0)
        lit_pct = data.get("lit_pct", 0)
        if lit_pct >= high:
            return 0   # fermé
        if lit_pct <= low:
            return 100  # ouvert
        # zone intermédiaire : interpolation linéaire
        ratio = (lit_pct - low) / (high - low)
        return round(100.0 - ratio * 100.0)


class TemperatureGuardStrategy(BaseStrategy):
    """Garde-fou température : ferme s'il fait chaud ET qu'il y a du soleil."""

    name = "temperature_guard"
    label = "Garde-fou température (chaud+soleil=fermé)"

    def compute_position(self, data: dict) -> int:
        temp = data.get("temperature")
        lit_pct = data.get("lit_pct", 0)
        temp_threshold = data.get("temp_threshold", 28.0)
        lit_threshold = data.get("lit_threshold", 20.0)
        if temp is not None and temp >= temp_threshold and lit_pct >= lit_threshold:
            return _block_all_position(data)
        return 100


class PrivacyNightStrategy(BaseStrategy):
    """Intimité nocturne : ferme la nuit, laisse ouvert le jour."""

    name = "privacy_night"
    label = "Intimité nocturne (fermé la nuit)"

    def compute_position(self, data: dict) -> int:
        h = data.get("solar_altitude", 0)
        if h is not None and h < 0:
            return 0
        return 100


class TargetIlluminationStrategy(BaseStrategy):
    """Cible d'ensoleillement précis : maintient un % d'éclairement donné."""

    name = "target_illumination"
    label = "Cible d'ensoleillement"

    def compute_position(self, data: dict) -> int:
        target = data.get("target_illumination", 30.0)
        return search_cover_position(data, target)


class AlwaysClosedStrategy(BaseStrategy):
    """Toujours fermé — isolation thermique, absence prolongée."""

    name = "always_closed"
    label = "Toujours fermé"

    def compute_position(self, data: dict) -> int:
        return 0


class AlwaysOpenStrategy(BaseStrategy):
    """Toujours ouvert — lumière naturelle maximale."""

    name = "always_open"
    label = "Toujours ouvert"

    def compute_position(self, data: dict) -> int:
        return 100


class LuxTargetStrategy(BaseStrategy):
    """Régulation par capteur lux intérieur — seuil + hystérésis + pas fixe."""

    name = "lux_target"
    label = "Cible lux intérieur (capteur)"

    def compute_position(self, data: dict) -> int:
        lux = data.get("lux_value")
        cur = data.get("current_position", 100)
        high = data.get("lux_high", 5000)
        low = data.get("lux_low", 3000)
        step = data.get("lux_step", 10)

        if lux is None:
            return cur

        if lux > high:
            return max(0, cur - step)
        if lux < low:
            return min(100, cur + step)
        return cur


# ---------------------------------------------------------------------------
# Registre
# ---------------------------------------------------------------------------

STRATEGIES: dict[str, BaseStrategy] = {
    "winter_passive": WinterPassiveStrategy(),
    "proportional": ProportionalStrategy(),
    "threshold": ThresholdStrategy(),
    "temperature_guard": TemperatureGuardStrategy(),
    "privacy_night": PrivacyNightStrategy(),
    "target_illumination": TargetIlluminationStrategy(),
    "block_all": BlockAllStrategy(),
    "always_closed": AlwaysClosedStrategy(),
    "always_open": AlwaysOpenStrategy(),
    "lux_target": LuxTargetStrategy(),
}

STRATEGY_OPTIONS = {k: v.label for k, v in STRATEGIES.items()}


def get_strategy(name: str) -> BaseStrategy:
    return STRATEGIES.get(name, STRATEGIES["block_all"])