"""Tests unitaires pour le moteur de calcul solaire."""

import math
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC))

import solar_math


def approx(val: float, digits: int = 4) -> float:
    return round(val, digits)


class TestD2R:
    def test_zero(self):
        assert solar_math.d2r(0) == 0.0

    def test_180(self):
        assert approx(solar_math.d2r(180)) == approx(math.pi)

    def test_90(self):
        assert approx(solar_math.d2r(90)) == approx(math.pi / 2)

    def test_360(self):
        assert approx(solar_math.d2r(360)) == approx(2 * math.pi)

    def test_negative(self):
        assert approx(solar_math.d2r(-90)) == approx(-math.pi / 2)


class TestR2D:
    def test_zero(self):
        assert solar_math.r2d(0) == 0.0

    def test_pi(self):
        assert approx(solar_math.r2d(math.pi)) == 180.0

    def test_pi_over_2(self):
        assert approx(solar_math.r2d(math.pi / 2)) == 90.0

    def test_negative(self):
        assert approx(solar_math.r2d(-math.pi / 2)) == -90.0

    def test_two_pi(self):
        assert approx(solar_math.r2d(2 * math.pi)) == 360.0


class TestNormAngle180:
    def test_zero(self):
        assert solar_math.norm_angle180(0) == 0.0

    def test_190(self):
        assert solar_math.norm_angle180(190) == -170.0

    def test_neg_190(self):
        assert solar_math.norm_angle180(-190) == 170.0

    def test_355(self):
        assert solar_math.norm_angle180(355) == -5.0

    def test_180(self):
        assert solar_math.norm_angle180(180) == -180.0

    def test_neg_180(self):
        assert solar_math.norm_angle180(-180) == -180.0

    def test_540(self):
        assert solar_math.norm_angle180(540) == -180.0

    def test_neg_540(self):
        assert solar_math.norm_angle180(-540) == -180.0

    def test_90(self):
        assert solar_math.norm_angle180(90) == 90.0


class TestHorizonDip:
    def test_zero_altitude(self):
        assert solar_math.horizon_dip(0) == 0.0

    def test_negative_altitude(self):
        assert solar_math.horizon_dip(-10) == 0.0

    def test_200m(self):
        dip = solar_math.horizon_dip(200)
        # ~0.45° pour 200m
        assert 0.4 < dip < 0.5

    def test_1000m(self):
        dip = solar_math.horizon_dip(1000)
        # ~1.0° pour 1000m
        assert 0.9 < dip < 1.1

    def test_high_altitude(self):
        dip = solar_math.horizon_dip(8848)
        # ~3.0° pour l'Everest
        assert 2.5 < dip < 3.5


class TestComputeWindow:
    def test_behind_azimuth(self):
        """Soleil derrière le mur (gamma > 90°)."""
        result = solar_math.compute_window(
            h=45, As=300, An=180, W=2, Hw=1.5, e=0.25
        )
        assert result["behind"] is True
        assert result["lit_pct"] == 0.0
        assert result["d_lat"] == 0.0
        assert result["d_vert"] == 0.0

    def test_behind_below_horizon(self):
        """Soleil sous l'horizon."""
        result = solar_math.compute_window(
            h=-10, As=180, An=180, W=2, Hw=1.5, e=0.25
        )
        assert result["behind"] is True
        assert result["lit_pct"] == 0.0

    def test_full_sun(self):
        """Plein soleil, pas d'embrasure."""
        result = solar_math.compute_window(
            h=45, As=180, An=180, W=2, Hw=1.5, e=0
        )
        assert result["behind"] is False
        assert result["gamma"] == 0.0
        assert approx(result["hp"]) == 45.0
        assert result["d_lat"] == 0.0
        assert result["d_vert"] == 0.0
        assert approx(result["lit_pct"]) == 100.0

    def test_wall_shadow(self):
        """Ombre portée de l'embrasure."""
        result = solar_math.compute_window(
            h=45, As=210, An=180, W=2, Hw=1.5, e=0.5
        )
        # gamma = 30°, d_lat = 0.5 * tan(30°) ≈ 0.289
        assert result["behind"] is False
        assert approx(result["gamma"]) == 30.0
        assert result["d_lat"] > 0
        assert result["d_vert"] > 0
        assert 0 < result["lit_pct"] < 100

    def test_wall_shadow_sun_from_left(self):
        """Azimut négatif (soleil à gauche de la normale)."""
        result = solar_math.compute_window(
            h=45, As=150, An=180, W=2, Hw=1.5, e=0.5
        )
        # gamma = -30°
        assert result["behind"] is False
        assert approx(result["gamma"]) == -30.0
        assert result["d_lat"] > 0
        assert 0 < result["lit_pct"] < 100

    def test_screen_blocks_all(self):
        """Mur écran qui bloque tout."""
        # h bas → ombre longue : y_ombre = 2 - 5*tan(5°) = 1.56 > Hw=1.5
        result = solar_math.compute_window(
            h=5, As=180, An=180, W=2, Hw=1.5, e=0,
            D=5, Hm=2,
        )
        assert result["behind"] is False
        assert result["screen_blocks_all"] is True
        assert result["lit_pct"] == 0.0

    def test_screen_partial(self):
        """Mur écran qui bloque partiellement."""
        result = solar_math.compute_window(
            h=30, As=180, An=180, W=2, Hw=1.5, e=0,
            D=3, Hm=2,
        )
        assert result["behind"] is False
        assert result["screen_blocks_all"] is False
        # y_ombre = 2 - 3*tan(30°) = 2 - 1.732 = 0.268
        assert 0 < result["y_ombre"] < 1.5

    def test_screen_partial_visible(self):
        """Mur écran bas avec soleil haut : ne bloque pas."""
        result = solar_math.compute_window(
            h=60, As=180, An=180, W=2, Hw=1.5, e=0,
            D=3, Hm=1,
        )
        # hp = 60°, y_ombre = 1 - 3*tan(60°) = 1 - 3*1.732 = -4.196
        # y_ombre = max(0, min(1.5, -4.196)) = 0
        assert result["behind"] is False
        assert result["screen_blocks_all"] is False
        assert result["y_ombre"] == 0.0
        assert approx(result["lit_pct"]) == 100.0

    def test_screen_blocks_upper_part(self):
        """Mur écran bloque la partie haute de la fenêtre."""
        result = solar_math.compute_window(
            h=30, As=180, An=180, W=2, Hw=1.5, e=0,
            D=2, Hm=1.5,
        )
        # hp = 30°, y_ombre = 1.5 - 2*tan(30°) = 1.5 - 2*0.577 = 0.346
        assert result["behind"] is False
        assert result["screen_blocks_all"] is False
        assert approx(result["y_ombre"], 1) == approx(0.346, 1)

    def test_zero_area(self):
        """Fenêtre de taille nulle."""
        result = solar_math.compute_window(
            h=45, As=180, An=180, W=0, Hw=0, e=0.25
        )
        assert result["behind"] is False
        assert result["lit_pct"] == 0.0
        assert result["lit_area_m2"] == 0.0

    def test_negative_elevation_above_dip(self):
        """Soleil juste sous l'horizon mais au-dessus du dip."""
        # altitude 500m + ground 1500m = 2000m -> dip ≈ 40'
        # h = -0.5°, dip = 1.44° => h > -dip donc PAS behind
        result = solar_math.compute_window(
            h=-0.5, As=180, An=180, W=2, Hw=1.5, e=0.25,
            altitude=500, ground_altitude=1500,
        )
        assert result["behind"] is False

    def test_negative_elevation_below_dip(self):
        """Soleil sous le dip horizon."""
        # h = -3°, dip ≈ 40' => h < -dip => behind
        result = solar_math.compute_window(
            h=-3, As=180, An=180, W=2, Hw=1.5, e=0.25,
            altitude=10, ground_altitude=208,
        )
        assert result["behind"] is True

    def test_horizontal_sun_equator(self):
        """Soleil à l'horizon (h=0)."""
        result = solar_math.compute_window(
            h=0, As=180, An=180, W=2, Hw=1.5, e=0,
        )
        # h=0, dip=0, gamma=0 -> behind if h <= -dip -> 0 <= 0 -> behind
        assert result["behind"] is True

    def test_compute_theta(self):
        """Vérifie la présence et la plage de theta."""
        result = solar_math.compute_window(
            h=45, As=180, An=180, W=2, Hw=1.5, e=0
        )
        assert result["theta"] is not None
        assert 0 <= result["theta"] <= 90

    def test_total_altitude(self):
        """Vérifie le calcul de l'altitude totale."""
        result = solar_math.compute_window(
            h=45, As=180, An=180, W=2, Hw=1.5, e=0.25,
            altitude=10, ground_altitude=208,
        )
        assert result["total_altitude"] == 218
        assert result["ground_altitude"] == 208