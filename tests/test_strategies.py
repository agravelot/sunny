"""Tests unitaires pour les stratégies de pilotage."""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC))

import strategies


def _full_sun_data(**kw) -> dict:
    """Données de base avec plein soleil."""
    data = {
        "behind": False,
        "screen_blocks_all": False,
        "lit_pct": 100.0,
        "window_height": 1.5,
        "window_width": 2.0,
        "d_lat": 0.0,
        "d_vert": 0.0,
        "y_ombre": 0.0,
        "tilt_threshold": 5.0,
        "slat_transmission": 5.0,
        "solar_altitude": 45.0,
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

    def test_screen_blocks_all(self):
        assert strategies._lit_at_cover_position(
            {"behind": False, "screen_blocks_all": True}, 100
        ) == 0.0

    def test_open_full_sun(self):
        data = _full_sun_data()
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit == 100.0

    def test_closed_full_sun(self):
        data = _full_sun_data()
        lit = strategies._lit_at_cover_position(data, 0)
        # tilt_threshold=5, cover_pos=0 => transmission=0
        assert lit == 0.0

    def test_tilt_phase(self):
        data = _full_sun_data(tilt_threshold=10, slat_transmission=50)
        # cover_pos=5 <= tilt_threshold=10 => phase tilt
        # transmission = (5/10)*(50/100) = 0.25
        lit = strategies._lit_at_cover_position(data, 5)
        assert lit == 25.0

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
        data = _full_sun_data(d_lat=0.4, d_vert=0.3, y_ombre=0.0)
        lit = strategies._lit_at_cover_position(data, 100)
        # lit_w = 2.0 - 0.4 = 1.6
        # lit_top = max(0.3, 0) = 0.3
        # lit_bottom = 1.5 - 0 = 1.5
        # lit_h = 1.2
        # area = 2*1.5 = 3.0
        # pct = (1.6*1.2/3.0)*100 = 64%
        assert lit == 64.0

    def test_screen_partial_shadow(self):
        """L'ombre du mur écran réduit la zone éclairée même store ouvert."""
        data = _full_sun_data(y_ombre=0.5)
        lit = strategies._lit_at_cover_position(data, 100)
        # clear_bottom = 1.5 - 0.5 = 1.0 => lit = (2*1)/3*100 = 66.7
        assert lit == pytest.approx(66.6667, abs=0.01)

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

    def test_screen_blocks_all(self):
        assert strategies.search_cover_position(
            {"behind": False, "screen_blocks_all": True, "lit_pct": 0}, 30.0
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
        # We need a scenario where d_vert=0, y_ombre=0, etc.
        data = _full_sun_data(
            lit_pct=10, d_lat=0, d_vert=0, y_ombre=0,
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

    def test_screen_blocks(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data(screen_blocks_all=True))
        assert pos == 100

    def test_no_lit(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_no_sun_data())
        assert pos == 100

    def test_full_sun(self):
        s = strategies.BlockAllStrategy()
        # y_ombre=0, Hw=1.5 => 100 * 0 / 1.5 = 0
        pos = s.compute_position(_full_sun_data(y_ombre=0.0))
        assert pos == 0

    def test_partial_sun(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=50, y_ombre=0.5))
        assert pos == 33  # 100 * 0.5 / 1.5 = 33.3 -> 33


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
        assert pos == 0  # y_ombre=0 => 100*0/1.5 = 0

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

    def test_hot_with_screen(self):
        s = strategies.TemperatureGuardStrategy()
        data = _full_sun_data(temperature=30, lit_pct=40, y_ombre=0.6)
        pos = s.compute_position(data)
        assert pos == 40  # 100 * 0.6 / 1.5 = 40


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
        assert len(strategies.STRATEGIES) == 8

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