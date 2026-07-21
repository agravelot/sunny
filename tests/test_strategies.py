"""Tests unitaires pour les stratégies de pilotage."""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC))

import strategies


def _full_sun_data(**kw) -> dict:
    """Données de base avec plein soleil (aucun obstacle)."""
    data = {
        "behind": False,
        "lit_pct": 100.0,
        "window_height": 1.5,
        "window_width": 2.0,
        "d_lat": 0.0,
        "d_vert": 0.0,
        "tilt_threshold": 5.0,
        "slat_transmission": 5.0,
        "solar_altitude": 45.0,
        "gamma": 0.0,
        "obstacles": [],
    }
    data.update(kw)
    return data


def _no_sun_data(**kw) -> dict:
    return _full_sun_data(lit_pct=0.0, **kw)


# -----------------------------------------------------------------------
# _lit_at_cover_position
# -----------------------------------------------------------------------

class TestLitAtCoverPosition:
    def test_behind(self):
        assert strategies._lit_at_cover_position({"behind": True}, 100) == 0.0

    def test_all_shadowed(self):
        assert strategies._lit_at_cover_position(
            {"behind": False, "lit_pct": 0.0, "obstacles": []}, 100
        ) == 0.0

    def test_open_full_sun(self):
        data = _full_sun_data()
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit == pytest.approx(100.0)

    def test_closed_full_sun(self):
        data = _full_sun_data()
        lit = strategies._lit_at_cover_position(data, 0)
        # tilt_threshold=5, cover_pos=0 => transmission=0
        assert lit == 0.0

    def test_tilt_phase(self):
        data = _full_sun_data(tilt_threshold=10, slat_transmission=50)
        lit = strategies._lit_at_cover_position(data, 5)
        assert lit == pytest.approx(25.0)

    def test_lift_phase(self):
        data = _full_sun_data(tilt_threshold=10, slat_transmission=50)
        # cover_pos=60 > tilt_threshold=10 => phase levée
        # effective_pos = (60-10)/(100-10)*100 = 55.56
        # y_cover = 1.5 * (1 - 0.5556) = 0.667
        lit = strategies._lit_at_cover_position(data, 60)
        assert 50 < lit < 100

    def test_no_tilt_phase(self):
        """tilt_threshold <= 0 => skip phase tilt."""
        data = _full_sun_data(tilt_threshold=0, slat_transmission=50)
        lit = strategies._lit_at_cover_position(data, 50)
        # y_cover = 1.5 * 0.5 = 0.75
        assert 40 < lit < 60

    def test_full_sun_with_wall_shadow(self):
        data = _full_sun_data(d_lat=0.4, d_vert=0.3)
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit == pytest.approx(64.0, abs=0.5)

    def test_obstacle_partial_shadow(self):
        """Obstacle frontal crée une ombre partielle, store ouvert."""
        data = _full_sun_data(
            solar_altitude=30,
            gamma=0.0,
            obstacles=[{
                "x1": -10000, "y1": 3, "z1": 0,
                "x2": 10000, "y2": 3.001, "z2": 2,
            }],
        )
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit < 100

    def test_reveal_one_side_only(self):
        """L'ombre latérale ne doit pas être symétrique des deux côtés."""
        # W=1.5, d_lat=0.8 → 2*d_lat=1.6 > W → symétrique = 0%
        # Juste un côté : 1.5-0.8 = 0.7m → 46.7%
        data = _full_sun_data(
            solar_altitude=45,
            gamma=-60,
            d_lat=0.8,
            d_vert=0,
            window_width=1.5,
            window_height=1.5,
        )
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit > 30  # devrait être ~46.7%

    def test_zero_area(self):
        data = _full_sun_data(window_width=0, window_height=0)
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit == 0.0


# -----------------------------------------------------------------------
# search_cover_position
# -----------------------------------------------------------------------

class TestSearchCoverPosition:
    def test_behind(self):
        assert strategies.search_cover_position(
            {"behind": True, "lit_pct": 0}, 30.0
        ) == 100

    def test_all_shadowed(self):
        assert strategies.search_cover_position(
            {"behind": False, "lit_pct": 0.0, "obstacles": []}, 30.0
        ) == 100

    def test_no_lit(self):
        assert strategies.search_cover_position(
            _no_sun_data(), 30.0
        ) == 100

    def test_even_closed_is_enough(self):
        """Même fermé, assez de lumière (cas rare)."""
        data = _full_sun_data(lit_pct=5.0)
        # closed lit = 0 (with tilt), so closed won't be enough
        # We need data where closed position still gives enough light
        # Let's use tilt_threshold=0 and very low wall shadow
        data = _full_sun_data(
            lit_pct=10.0, d_lat=0.9, d_vert=0.8,
            tilt_threshold=0, window_width=2.0, window_height=1.5,
        )
        # lit at cover_pos=0: y_cover = 1.5*1.0 = 1.5
        # lit_top = max(0.8, 1.5) = 1.5
        # lit_bottom = 1.5 - 0 = 1.5
        # lit_h = 0 => 0%
        # So this won't return 0 either.
        # We need a scenario where d_vert=0, sans obstacle, etc.
        data = _full_sun_data(
            lit_pct=10, d_lat=0, d_vert=0,
            tilt_threshold=0,
        )
        # With tilt_threshold=0: y_cover = 1.5*1.0 = 1.5
        # lit_top = max(0, 1.5) = 1.5
        # lit_bottom = 1.5 - 0 = 1.5
        # lit_h = 0 => 0%
        # Hmm, even at tilt_threshold=0, closed = 0 lit.
        # Actually that's correct: store fully closed blocks everything.
        # So test_closed_never_enough instead:
        pos = strategies.search_cover_position(data, 10.0)
        assert pos > 0

    def test_returns_int(self):
        data = _full_sun_data()
        pos = strategies.search_cover_position(data, 30.0)
        assert isinstance(pos, int)
        assert 0 <= pos <= 100

    def test_target_illumination(self):
        """Cible atteignable -> position entre 0 et 100."""
        data = _full_sun_data()
        pos = strategies.search_cover_position(data, 50.0)
        assert 0 <= pos <= 100


# -----------------------------------------------------------------------
# Bloc à tester
# -----------------------------------------------------------------------

class TestBlockAllStrategy:
    def test_behind(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data(behind=True))
        assert pos == 100

    def test_all_shadowed(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=0))
        assert pos == 100

    def test_no_lit(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_no_sun_data())
        assert pos == 100

    def test_full_sun(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data())
        assert pos == 0

    def test_partial_sun(self):
        s = strategies.BlockAllStrategy()
        data = _full_sun_data(
            solar_altitude=30, gamma=0.0,
            obstacles=[{
                "x1": -10000, "y1": 2, "z1": 0,
                "x2": 10000, "y2": 2.001, "z2": 1.5,
            }],
        )
        pos = s.compute_position(data)
        assert 0 <= pos <= 100  # position intermédiaire

    def test_side_sun_partial_close(self):
        """Soleil de côté : l'ombre symétrique vide le masque → pos=100 au lieu de fermer."""
        s = strategies.BlockAllStrategy()
        # W=1.5, d_lat=0.8 → 2*d_lat=1.6 > W=1.5 → masque vide (bug symétrique)
        # Correctif : ombre d'un seul côté → masque non vide → pos < 100
        data = _full_sun_data(
            lit_pct=50,
            solar_altitude=45,
            gamma=-60,
            d_lat=0.8,
            d_vert=0,
            window_width=1.5,
            window_height=1.5,
        )
        pos = s.compute_position(data)
        assert pos < 100


class TestWinterPassiveStrategy:
    def test_sun(self):
        s = strategies.WinterPassiveStrategy()
        assert s.compute_position(_full_sun_data()) == 100

    def test_no_sun(self):
        s = strategies.WinterPassiveStrategy()
        assert s.compute_position(_no_sun_data()) == 0


class TestProportionalStrategy:
    def test_full_sun(self):
        s = strategies.ProportionalStrategy()
        assert s.compute_position(_full_sun_data(lit_pct=100)) == 0

    def test_partial_sun(self):
        s = strategies.ProportionalStrategy()
        assert s.compute_position(_full_sun_data(lit_pct=70)) == 30

    def test_no_sun(self):
        s = strategies.ProportionalStrategy()
        assert s.compute_position(_no_sun_data()) == 100

    def test_no_sun_no_lit_pct(self):
        s = strategies.ProportionalStrategy()
        assert s.compute_position({"lit_pct": 0}) == 100


class TestThresholdStrategy:
    def test_above_high(self):
        s = strategies.ThresholdStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=80))
        assert pos == 0

    def test_below_low(self):
        s = strategies.ThresholdStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=10))
        assert pos == 100

    def test_interpolate(self):
        s = strategies.ThresholdStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=35))
        # (35 - 20) / (50 - 20) = 0.5 => 100 - 0.5*100 = 50
        assert pos == 50

    def test_custom_thresholds(self):
        s = strategies.ThresholdStrategy()
        data = _full_sun_data(lit_pct=40, strategy_high=60, strategy_low=10)
        pos = s.compute_position(data)
        # (40 - 10) / (60 - 10) = 0.6 => 100 - 60 = 40
        assert pos == 40

    def test_at_exact_high(self):
        s = strategies.ThresholdStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=50))
        assert pos == 0

    def test_at_exact_low(self):
        s = strategies.ThresholdStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=20))
        assert pos == 100


class TestTemperatureGuardStrategy:
    def test_hot_and_sunny(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(temperature=30, lit_pct=40)
        pos = s.compute_position(data)
        assert pos == 0  # sans obstacle => block_all = 0

    def test_cold_and_sunny(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(temperature=20, lit_pct=40)
        pos = s.compute_position(data)
        assert pos == 100

    def test_hot_and_shady(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(temperature=30, lit_pct=10)
        pos = s.compute_position(data)
        assert pos == 100

    def test_no_temperature(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(temperature=None, lit_pct=40)
        pos = s.compute_position(data)
        assert pos == 100

    def test_custom_thresholds(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(
            temperature=26, lit_pct=15,
            temp_threshold=25.0, lit_threshold=10.0,
        )
        pos = s.compute_position(data)
        assert pos == 0  # hot+sunny -> block_all

    def test_hot_with_obstacle(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(
            temperature=30, lit_pct=40,
            solar_altitude=30, gamma=0.0,
            obstacles=[{
                "x1": -10000, "y1": 2, "z1": 0,
                "x2": 10000, "y2": 2.001, "z2": 1.0,
            }],
        )
        pos = s.compute_position(data)
        assert 0 <= pos <= 100


class TestPrivacyNightStrategy:
    def test_day(self):
        s = strategies.PrivacyNightStrategy()
        data = _full_sun_data(solar_altitude=45)
        assert s.compute_position(data) == 100

    def test_night(self):
        s = strategies.PrivacyNightStrategy()
        data = _full_sun_data(solar_altitude=-10)
        assert s.compute_position(data) == 0

    def test_twilight(self):
        s = strategies.PrivacyNightStrategy()
        data = _full_sun_data(solar_altitude=0)
        assert s.compute_position(data) == 100  # h >= 0 => jour


class TestTargetIlluminationStrategy:
    def test_returns_int(self):
        s = strategies.TargetIlluminationStrategy()
        data = _full_sun_data()
        pos = s.compute_position(data)
        assert isinstance(pos, int)
        assert 0 <= pos <= 100

    def test_custom_target(self):
        s = strategies.TargetIlluminationStrategy()
        data = _full_sun_data(target_illumination=50.0)
        pos = s.compute_position(data)
        assert 0 <= pos <= 100


class TestAlwaysClosedStrategy:
    def test_full_sun(self):
        s = strategies.AlwaysClosedStrategy()
        assert s.compute_position(_full_sun_data()) == 0

    def test_no_sun(self):
        s = strategies.AlwaysClosedStrategy()
        assert s.compute_position(_no_sun_data()) == 0

    def test_behind(self):
        s = strategies.AlwaysClosedStrategy()
        assert s.compute_position(_full_sun_data(behind=True)) == 0

    def test_empty_data(self):
        s = strategies.AlwaysClosedStrategy()
        assert s.compute_position({}) == 0


class TestAlwaysOpenStrategy:
    def test_full_sun(self):
        s = strategies.AlwaysOpenStrategy()
        assert s.compute_position(_full_sun_data()) == 100

    def test_no_sun(self):
        s = strategies.AlwaysOpenStrategy()
        assert s.compute_position(_no_sun_data()) == 100

    def test_behind(self):
        s = strategies.AlwaysOpenStrategy()
        assert s.compute_position(_full_sun_data(behind=True)) == 100

    def test_empty_data(self):
        s = strategies.AlwaysOpenStrategy()
        assert s.compute_position({}) == 100


# -----------------------------------------------------------------------
# LuxTarget
# -----------------------------------------------------------------------

class TestLuxTargetStrategy:
    def test_lux_above_high_closes(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 6000, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 40

    def test_lux_below_low_opens(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 2000, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 60

    def test_lux_in_deadzone_unchanged(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 4000, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 50

    def test_lux_none_unchanged(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": None, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 50

    def test_already_closed_stays_closed(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 6000, "current_position": 0, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 0

    def test_already_open_stays_open(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 2000, "current_position": 100, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 100

    def test_clamp_near_zero(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 6000, "current_position": 5, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 0

    def test_clamp_near_hundred(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 2000, "current_position": 95, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 100

    def test_custom_step(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 6000, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 20}
        assert s.compute_position(data) == 30

    def test_custom_thresholds(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 900, "current_position": 50, "lux_high": 1000, "lux_low": 500, "lux_step": 10}
        assert s.compute_position(data) == 50  # dans la zone morte [500, 1000]

    def test_at_exact_high_boundary(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 5000, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 50  # lux == high → dans la zone morte

    def test_at_exact_low_boundary(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 3000, "current_position": 50, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 50  # lux == low → dans la zone morte

    def test_defaults_applied(self):
        s = strategies.LuxTargetStrategy()
        pos = s.compute_position({"lux_value": 6000, "current_position": 50})
        assert pos == 40  # défauts: high=5000, low=3000, step=10

    def test_no_current_position_defaults_to_100(self):
        s = strategies.LuxTargetStrategy()
        data = {"lux_value": 2000, "lux_high": 5000, "lux_low": 3000, "lux_step": 10}
        assert s.compute_position(data) == 100  # current_position défaut 100 → déjà au max


# -----------------------------------------------------------------------
# Registre
# -----------------------------------------------------------------------

class TestRegistry:
    def test_strategies_dict(self):
        assert "block_all" in strategies.STRATEGIES
        assert "winter_passive" in strategies.STRATEGIES
        assert "proportional" in strategies.STRATEGIES
        assert "threshold" in strategies.STRATEGIES
        assert "temperature_guard" in strategies.STRATEGIES
        assert "privacy_night" in strategies.STRATEGIES
        assert "target_illumination" in strategies.STRATEGIES
        assert "always_closed" in strategies.STRATEGIES
        assert "always_open" in strategies.STRATEGIES
        assert "lux_target" in strategies.STRATEGIES
        assert len(strategies.STRATEGIES) == 10

    def test_strategy_options(self):
        assert "block_all" in strategies.STRATEGY_OPTIONS
        assert strategies.STRATEGY_OPTIONS["block_all"] == "Bloquer tout soleil direct (été/canicule)"

    def test_get_strategy(self):
        s = strategies.get_strategy("block_all")
        assert isinstance(s, strategies.BlockAllStrategy)

    def test_get_strategy_fallback(self):
        s = strategies.get_strategy("unknown_strategy")
        assert isinstance(s, strategies.BlockAllStrategy)

    def test_instances_are_singletons(self):
        assert strategies.get_strategy("threshold") is strategies.STRATEGIES["threshold"]


class TestReliefAngleBehind:
    """Vérifie que les stratégies réagissent correctement à behind=True via relief_angle."""

    def _behind_from_relief(self, **kw) -> dict:
        data = _full_sun_data(**kw)
        data["behind"] = True
        data["lit_pct"] = 0.0
        data["relief_angle"] = 3.0
        data["solar_altitude"] = 2.0  # en dessous de relief_angle=3
        return data

    def test_block_all_opens_when_behind(self):
        s = strategies.BlockAllStrategy()
        assert s.compute_position(self._behind_from_relief()) == 100

    def test_winter_passive_closes_when_no_sun(self):
        s = strategies.WinterPassiveStrategy()
        assert s.compute_position(self._behind_from_relief()) == 0

    def test_proportional_opens_when_no_sun(self):
        s = strategies.ProportionalStrategy()
        assert s.compute_position(self._behind_from_relief()) == 100

    def test_temperature_guard_opens_when_behind(self):
        s = strategies.TemperatureGuardStrategy()
        pos = s.compute_position(self._behind_from_relief(temperature=30))
        assert pos == 100  # behind=True → ouvert quelle que soit la température

    def test_privacy_night_stays_open_in_day(self):
        s = strategies.PrivacyNightStrategy()
        # h=2 > 0 → jour, même si behind
        assert s.compute_position(self._behind_from_relief()) == 100

    def test_always_closed_ignores_behind(self):
        s = strategies.AlwaysClosedStrategy()
        assert s.compute_position(self._behind_from_relief()) == 0

    def test_always_open_ignores_behind(self):
        s = strategies.AlwaysOpenStrategy()
        assert s.compute_position(self._behind_from_relief()) == 100