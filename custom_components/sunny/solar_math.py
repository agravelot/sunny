"""Moteur de calcul solaire — portage du simulateur HTML vers Python."""

import math


def d2r(d: float) -> float:
    return d * math.pi / 180


def r2d(r: float) -> float:
    return r * 180 / math.pi


def norm_angle180(a: float) -> float:
    return ((a + 180) % 360 + 360) % 360 - 180


def horizon_dip(altitude_m: float) -> float:
    if altitude_m <= 0:
        return 0.0
    return r2d(math.acos(6371.0 / (6371.0 + altitude_m / 1000.0)))


def compute_window(
    h: float,
    As: float,
    An: float,
    W: float,
    Hw: float,
    e: float = 0.25,
    D: float = 0.0,
    Hm: float = 0.0,
    altitude: float = 0.0,
) -> dict:
    dip = horizon_dip(altitude)
    gamma = norm_angle180(As - An)
    behind = h <= -dip or abs(gamma) >= 90

    result = {
        "solar_altitude": h,
        "solar_azimuth": As,
        "wall_azimuth": An,
        "window_width": W,
        "window_height": Hw,
        "gamma": gamma,
        "behind": behind,
        "horizon_dip": dip,
        "hp": None,
        "theta": None,
        "d_lat": 0.0,
        "d_vert": 0.0,
        "y_ombre": 0.0,
        "screen_blocks_all": False,
        "lit_area_m2": 0.0,
        "lit_pct": 0.0,
    }

    if behind:
        return result

    h_rad = d2r(h)
    g_rad = d2r(gamma)
    cos_g = math.cos(g_rad)
    theta = r2d(math.acos(max(-1.0, min(1.0, math.cos(h_rad) * cos_g))))
    tan_hp = math.tan(h_rad) / cos_g
    hp = r2d(math.atan(tan_hp))

    d_lat = max(0.0, e * math.tan(abs(g_rad)))
    w_utile = max(0.0, W - d_lat)
    d_vert = max(0.0, e * math.tan(d2r(max(hp, 0.0))))
    h_utile = max(0.0, Hw - d_vert)

    y_ombre = 0.0
    screen_blocks_all = False

    if D > 0:
        y_ombre = Hm - D * math.tan(d2r(hp))
        y_ombre = max(0.0, min(Hw, y_ombre))
        if y_ombre >= Hw:
            screen_blocks_all = True

    lit_height = max(0.0, h_utile - y_ombre)
    lit_width = w_utile
    area = W * Hw
    lit_area = lit_width * lit_height
    pct = (lit_area / area * 100.0) if area > 0 else 0.0

    result.update({
        "hp": hp,
        "theta": theta,
        "d_lat": d_lat,
        "d_vert": d_vert,
        "y_ombre": y_ombre,
        "screen_blocks_all": screen_blocks_all,
        "lit_area_m2": lit_area,
        "lit_pct": round(pct, 1),
    })

    return result