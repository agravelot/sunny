"""Stratégies de pilotage des stores."""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Classe de base pour une stratégie de pilotage."""

    name: str
    label: str = ""

    @abstractmethod
    def compute_position(self, data: dict) -> int:
        """Calcule la position désirée du store (0=fermé, 100=ouvert)."""


def _lit_at_cover_position(data: dict, cover_pos: float) -> float:
    """Calcule le pourcentage d'éclairement si le store est à cover_pos %.
    
    Modèle avec phase tilt : les premiers pourcentages d'ouverture basculent
    les lamelles sans lever le bas du store, laissant passer une fraction de
    lumière filtrée (sans éblouissement). Au-delà du seuil tilt_threshold,
    le bas du store se lève physiquement.
    """
    if data.get("behind") or data.get("screen_blocks_all"):
        return 0.0
    Hw = data.get("window_height", 1.0)
    W = data.get("window_width", 1.0)
    d_vert = data.get("d_vert", 0.0)
    y_ombre = data.get("y_ombre", 0.0)
    d_lat = data.get("d_lat", 0.0)
    tilt_threshold = data.get("tilt_threshold", 5.0)
    slat_transmission = data.get("slat_transmission", 5.0)
    area = W * Hw
    if area <= 0:
        return 0.0

    lit_w = max(0.0, W - d_lat)

    if tilt_threshold <= 0 or tilt_threshold >= 100:
        # Comportement original sans phase tilt
        y_cover = Hw * (1.0 - cover_pos / 100.0)
        lit_top = max(d_vert, y_cover)
        lit_bottom = Hw - y_ombre
        lit_h = max(0.0, lit_bottom - lit_top)
        return (lit_w * lit_h / area * 100.0)

    if cover_pos <= tilt_threshold:
        # Phase tilt : store complètement baissé, lamelles basculent progressivement
        transmission = (cover_pos / tilt_threshold) * (slat_transmission / 100.0)
        base_lit_top = d_vert
        base_lit_bottom = Hw - y_ombre
        base_lit_h = max(0.0, base_lit_bottom - base_lit_top)
        return (lit_w * base_lit_h * transmission / area * 100.0)
    else:
        # Phase levée : lamelles ouvertes, le bas du store se lève
        effective_pos = (cover_pos - tilt_threshold) / (100.0 - tilt_threshold) * 100.0
        y_cover = Hw * (1.0 - effective_pos / 100.0)

        # Zone dégagée (sous le store) : plein soleil direct
        clear_top = max(d_vert, y_cover)
        clear_bottom = Hw - y_ombre
        clear_h = max(0.0, clear_bottom - clear_top)
        clear_lit = lit_w * clear_h

        # Zone couverte par le store (lamelles ouvertes) : lumière filtrée
        slat_top = d_vert
        slat_bottom = min(y_cover, Hw - y_ombre)
        slat_h = max(0.0, slat_bottom - slat_top)
        slat_lit = lit_w * slat_h * (slat_transmission / 100.0)

        return ((clear_lit + slat_lit) / area * 100.0)


def search_cover_position(data: dict, target_pct: float) -> int:
    """Recherche binaire optimisée (5% + binaire) de la position du store
    qui donne au moins target_pct % d'ensoleillement. Retourne 0-100."""
    if data.get("behind") or data.get("screen_blocks_all") or data.get("lit_pct", 0) == 0:
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
        if data.get("behind") or data.get("screen_blocks_all"):
            return 100
        lit_pct = data.get("lit_pct", 0)
        if lit_pct == 0:
            return 100
        y_ombre = data.get("y_ombre", 0.0)
        Hw = data.get("window_height", 1.0)
        if Hw <= 0:
            return 100
        pos = 100.0 * y_ombre / Hw
        return min(100, max(0, round(pos)))


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
            y_ombre = data.get("y_ombre", 0.0)
            Hw = data.get("window_height", 1.0)
            if Hw > 0 and y_ombre < Hw:
                pos = 100.0 * y_ombre / Hw
                return min(100, max(0, round(pos)))
            return 0
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
}

STRATEGY_OPTIONS = {k: v.label for k, v in STRATEGIES.items()}


def get_strategy(name: str) -> BaseStrategy:
    return STRATEGIES.get(name, STRATEGIES["block_all"])