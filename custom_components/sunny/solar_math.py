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


def _ray_box_intersect(
    px: float, py: float, pz: float,
    dx: float, dy: float, dz: float,
    obs: dict,
) -> bool:
    """Intersection rayon-boîte alignée (slab method).

    Retourne True si le rayon partant de (px, py, pz) dans la direction
    (dx, dy, dz) intersecte la boîte définie par l'obstacle.
    """
    xmin = min(obs["x1"], obs["x2"])
    xmax = max(obs["x1"], obs["x2"])
    ymin = min(obs["y1"], obs["y2"])
    ymax = max(obs["y1"], obs["y2"])
    zmin = min(obs["z1"], obs["z2"])
    zmax = max(obs["z1"], obs["z2"])

    t_near = float("-inf")
    t_far = float("inf")

    # Slab X
    if dx != 0.0:
        t1 = (xmin - px) / dx
        t2 = (xmax - px) / dx
        t_near = max(t_near, min(t1, t2))
        t_far = min(t_far, max(t1, t2))
    elif px < xmin or px > xmax:
        return False

    # Slab Y
    if dy != 0.0:
        t1 = (ymin - py) / dy
        t2 = (ymax - py) / dy
        t_near = max(t_near, min(t1, t2))
        t_far = min(t_far, max(t1, t2))
    elif py < ymin or py > ymax:
        return False

    # Slab Z
    if dz != 0.0:
        t1 = (zmin - pz) / dz
        t2 = (zmax - pz) / dz
        t_near = max(t_near, min(t1, t2))
        t_far = min(t_far, max(t1, t2))
    elif pz < zmin or pz > zmax:
        return False

    return t_near < t_far and t_near > 0.0  # t_near > 0 exclut les obstacles attachés à la façade (ailes)


def compute_window(
    h: float,
    As: float,
    An: float,
    W: float,
    Hw: float,
    e: float = 0.25,
    obstacles: list[dict] | None = None,
    altitude: float = 0.0,
    ground_altitude: float = 0.0,
) -> dict:
    dip = horizon_dip(ground_altitude + altitude)
    gamma = norm_angle180(As - An)
    behind = h <= -dip or abs(gamma) >= 90

    if obstacles is None:
        obstacles = []

    result = {
        "solar_altitude": h,
        "solar_azimuth": As,
        "wall_azimuth": An,
        "window_width": W,
        "window_height": Hw,
        "gamma": gamma,
        "behind": behind,
        "horizon_dip": dip,
        "ground_altitude": ground_altitude,
        "total_altitude": ground_altitude + altitude,
        "hp": None,
        "theta": None,
        "d_lat": 0.0,
        "d_vert": 0.0,
        "lit_area_m2": 0.0,
        "lit_pct": 0.0,
        "obstacles": obstacles,
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
    d_vert = max(0.0, e * math.tan(d2r(max(hp, 0.0))))

    result.update({
        "hp": hp,
        "theta": theta,
        "d_lat": d_lat,
        "d_vert": d_vert,
    })

    # Discrétisation proportionnelle à la taille de la fenêtre
    R = 100  # pts/m
    nx = max(1, int(W * R))
    nz = max(1, int(Hw * R))

    # Direction du rayon vers le soleil depuis l'origine (0,0,0)
    dir_x = math.sin(g_rad) * math.cos(h_rad)
    dir_y = math.cos(g_rad) * math.cos(h_rad)
    dir_z = math.sin(h_rad)

    lit_count = 0
    for ix in range(nx):
        x_w = (ix + 0.5) * W / nx
        for iz in range(nz):
            z_w = (iz + 0.5) * Hw / nz
            # Ombre d'embrasure
            if x_w < d_lat or x_w > W - d_lat:
                continue
            if z_w > Hw - d_vert:
                continue
            # Obstacles
            blocked = False
            for obs in obstacles:
                if _ray_box_intersect(x_w, 0.0, z_w, dir_x, dir_y, dir_z, obs):
                    blocked = True
                    break
            if not blocked:
                lit_count += 1

    area = W * Hw
    cell_area = area / (nx * nz)
    lit_area = lit_count * cell_area
    pct = (lit_count / (nx * nz) * 100.0) if (nx * nz) > 0 else 0.0

    result.update({
        "lit_area_m2": lit_area,
        "lit_pct": round(pct, 1),
    })

    return result