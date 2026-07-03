"""Stratégies de pilotage des stores."""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Classe de base pour une stratégie de pilotage."""

    name: str

    @abstractmethod
    def compute_position(self, data: dict) -> int:
        """Calcule la position désirée du store (0=fermé, 100=ouvert)."""


class BlockAllStrategy(BaseStrategy):
    """Bloque tout le soleil direct — été / canicule.

    Calcule la position du store nécessaire pour que la zone éclairée
    restante (après ombres du linteau et du mur écran) soit entièrement
    couverte par le store descendant depuis le haut.
    """

    name = "block_all"

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


STRATEGIES = {
    "block_all": BlockAllStrategy(),
}


def get_strategy(name: str) -> BaseStrategy:
    return STRATEGIES.get(name, STRATEGIES["block_all"])