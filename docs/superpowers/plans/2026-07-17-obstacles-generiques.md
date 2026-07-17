# Obstacles génériques 3D — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le mur-écran unique (`screen_distance`/`screen_height`) par un système d'obstacles 3D génériques définis par 2 coins `(x1,y1,z1,x2,y2,z2)`.

**Architecture:** Coordonnées locales fenêtre (x=gauche/droite, y=distance, z=hauteur). Discrétisation proportionnelle (100 pts/m) + intersection rayon-boîte (slab method). Migration auto `screen_distance>0` → obstacle frontal.

**Tech Stack:** Python 3, Home Assistant custom_component, pytest

## Global Constraints

- Langue : tout le code et les commentaires en français
- Pas d'imports Home Assistant dans `solar_math.py` ni `strategies.py`
- unique_id format : `{entry_id}_{window_id}_{window_name}_{suffix}` (jamais d'index positionnel)
- Tests n'importent pas Home Assistant, utilisent `sys.path` hack
- `pytest.ini` active `asyncio_mode = auto`
- Commit messages : concis, imperative, lowercase
- Simulateur HTML ignoré pour cette PR

---

### Task 1: Constantes — remplacer screen par obstacles

**Files:**
- Modify: `custom_components/sunny/const.py`

**Interfaces:**
- Produces: `CONF_OBSTACLES`, `DEFAULT_OBSTACLES`, `CONF_OBSTACLE_X1`, `CONF_OBSTACLE_Y1`, `CONF_OBSTACLE_Z1`, `CONF_OBSTACLE_X2`, `CONF_OBSTACLE_Y2`, `CONF_OBSTACLE_Z2`, `DEFAULT_OBSTACLE_X1`-`Z2`

- [ ] **Step 1: Remplacer les constantes dans const.py**

Ouvrir `custom_components/sunny/const.py`. Supprimer les lignes contenant `CONF_SCREEN_DISTANCE`, `CONF_SCREEN_HEIGHT`, `DEFAULT_SCREEN_DISTANCE`, `DEFAULT_SCREEN_HEIGHT`. Ajouter à la place :

```python
CONF_OBSTACLES = "obstacles"

CONF_OBSTACLE_X1 = "ox1"
CONF_OBSTACLE_Y1 = "oy1"
CONF_OBSTACLE_Z1 = "oz1"
CONF_OBSTACLE_X2 = "ox2"
CONF_OBSTACLE_Y2 = "oy2"
CONF_OBSTACLE_Z2 = "oz2"

DEFAULT_OBSTACLES: list = []
DEFAULT_OBSTACLE_X1 = 0.0
DEFAULT_OBSTACLE_Y1 = 0.0
DEFAULT_OBSTACLE_Z1 = 0.0
DEFAULT_OBSTACLE_X2 = 1.0
DEFAULT_OBSTACLE_Y2 = 1.0
DEFAULT_OBSTACLE_Z2 = 1.0
```

- [ ] **Step 2: Vérifier que le fichier est valide**

```bash
python3 -c "from custom_components.sunny import const; print(const.CONF_OBSTACLES)"
```
Expected: `obstacles`

- [ ] **Step 3: Commit**

```bash
git add custom_components/sunny/const.py
git commit -m "refactor: remplacer screen_distance/screen_height par obstacles dans les constantes"
```

---

### Task 2: Solar math — obstacle grid + ray-box

**Files:**
- Modify: `custom_components/sunny/solar_math.py:24-102`
- Modify: `tests/test_solar_math.py:105-256`

**Interfaces:**
- Consumes: `CONF_OBSTACLES` (via coordinator, not direct import)
- Produces: `_ray_box_intersect(px, py, pz, dx, dy, dz, obs) -> bool`, `compute_window(..., obstacles=[])`, result dict sans `y_ombre`/`screen_blocks_all`, avec `obstacles`

- [ ] **Step 1: Adapter les tests existants — remplacer screen par obstacles**

Dans `tests/test_solar_math.py`, remplacer les 4 tests screen (`test_screen_blocks_all`, `test_screen_partial`, `test_screen_partial_visible`, `test_screen_blocks_upper_part`) par des versions obstacle. Ajouter les nouveaux tests obstacle.

Remplacer tout le bloc à partir de `test_screen_blocks_all` (ligne 159) jusqu'à `test_zero_area` (exclu) par :

```python
def _frontal_obstacle(distance, height):
    """Construit un obstacle frontal équivalent à l'ancien mur-écran."""
    return {
        "x1": -10000, "y1": distance, "z1": 0,
        "x2": 10000,  "y2": distance + 0.001, "z2": height,
    }


class TestObstacles:
    def test_no_obstacles_full_sun(self):
        """Aucun obstacle, plein soleil."""
        result = solar_math.compute_window(
            h=45, As=180, An=180, W=2, Hw=1.5, e=0,
            obstacles=[],
        )
        assert result["lit_pct"] == 100.0

    def test_frontal_blocks_all(self):
        """Obstacle frontal qui bloque toute la fenêtre (équivalent screen_blocks_all)."""
        result = solar_math.compute_window(
            h=5, As=180, An=180, W=2, Hw=1.5, e=0,
            obstacles=[_frontal_obstacle(5, 2)],
        )
        assert result["behind"] is False
        assert result["lit_pct"] == 0.0

    def test_frontal_partial(self):
        """Obstacle frontal partiel (équivalent screen_partial)."""
        result = solar_math.compute_window(
            h=30, As=180, An=180, W=2, Hw=1.5, e=0,
            obstacles=[_frontal_obstacle(3, 2)],
        )
        assert result["behind"] is False
        assert 0 < result["lit_pct"] < 100

    def test_frontal_visible(self):
        """Obstacle frontal bas, soleil haut : ne bloque pas (équivalent screen_partial_visible)."""
        result = solar_math.compute_window(
            h=60, As=180, An=180, W=2, Hw=1.5, e=0,
            obstacles=[_frontal_obstacle(3, 1)],
        )
        assert result["behind"] is False
        assert result["lit_pct"] == 100.0

    def test_frontal_upper_part(self):
        """Obstacle frontal bloque la partie haute (équivalent screen_blocks_upper_part)."""
        result = solar_math.compute_window(
            h=30, As=180, An=180, W=2, Hw=1.5, e=0,
            obstacles=[_frontal_obstacle(2, 1.5)],
        )
        assert result["behind"] is False
        assert 0 < result["lit_pct"] < 100

    def test_lateral_wing_left_gamma_negative(self):
        """Aile à gauche, soleil à gauche (γ < 0) : ombre partielle."""
        result = solar_math.compute_window(
            h=45, As=150, An=180,  # gamma = -30
            W=2, Hw=1.5, e=0,
            obstacles=[{
                "x1": -10, "y1": 0, "z1": 0,
                "x2": 0.5, "y2": 3, "z2": 6,
            }],
        )
        assert result["behind"] is False
        assert 0 < result["lit_pct"] < 100

    def test_lateral_wing_left_gamma_positive(self):
        """Aile à gauche, soleil à droite (γ > 0) : pas d'ombre."""
        result = solar_math.compute_window(
            h=45, As=210, An=180,  # gamma = +30
            W=2, Hw=1.5, e=0,
            obstacles=[{
                "x1": -10, "y1": 0, "z1": 0,
                "x2": 0.5, "y2": 3, "z2": 6,
            }],
        )
        assert result["behind"] is False
        assert result["lit_pct"] == 100.0

    def test_lateral_wing_right_gamma_positive(self):
        """Aile à droite, soleil à droite (γ > 0) : ombre partielle."""
        result = solar_math.compute_window(
            h=45, As=210, An=180,  # gamma = +30
            W=2, Hw=1.5, e=0,
            obstacles=[{
                "x1": 1.5, "y1": 0, "z1": 0,
                "x2": 10000, "y2": 3, "z2": 6,
            }],
        )
        assert result["behind"] is False
        assert 0 < result["lit_pct"] < 100

    def test_multiple_obstacles_combined(self):
        """Mur frontal + aile latérale : ombres cumulées."""
        result = solar_math.compute_window(
            h=15, As=150, An=180,  # gamma = -30, soleil bas à gauche
            W=2, Hw=1.5, e=0,
            obstacles=[
                _frontal_obstacle(4, 2),
                {"x1": -10, "y1": 0, "z1": 0, "x2": 0.3, "y2": 2, "z2": 5},
            ],
        )
        assert result["behind"] is False
        assert 0 < result["lit_pct"] < 100

    def test_obstacle_discretization_proportional(self):
        """Vérifie que la grille s'adapte à la taille de la fenêtre."""
        # Grande fenêtre : 4m × 3m → 400 × 300 points
        result_big = solar_math.compute_window(
            h=45, As=180, An=180, W=4, Hw=3, e=0,
            obstacles=[],
        )
        assert approx(result_big["lit_pct"]) == 100.0
        # Petite fenêtre : doit aussi fonctionner
        result_small = solar_math.compute_window(
            h=45, As=180, An=180, W=0.5, Hw=0.4, e=0,
            obstacles=[],
        )
        assert approx(result_small["lit_pct"]) == 100.0
```

- [ ] **Step 2: Lancer les tests — doivent échouer**

```bash
python3 -m pytest tests/test_solar_math.py::TestObstacles -v
```
Expected: FAIL — `obstacles` parameter not accepted, or `D`/`Hm` removed but tests reference them

- [ ] **Step 3: Implémenter `_ray_box_intersect` dans solar_math.py**

Ajouter après la fonction `horizon_dip` :

```python
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

    return t_near < t_far and t_far > 0.0
```

- [ ] **Step 4: Remplacer `compute_window` — nouvelle signature + logique obstacles**

Remplacer la fonction `compute_window` (lignes 24-102) :

```python
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
```

- [ ] **Step 5: Mettre à jour les autres tests qui appellent `compute_window`**

Les appels existants dans `TestComputeWindow` n'utilisent pas `D`/`Hm` (tests `behind`, `full_sun`, `wall_shadow`, etc.) — ils passent les arguments positionnels. Comme on a retiré `D` et `Hm`, ces appels fonctionnent toujours (les paramètres supprimés étaient après `e` avec valeurs par défaut).

Vérifier que `test_zero_area` passe toujours (appel sans `D`/`Hm`).

- [ ] **Step 6: Lancer tous les tests solar_math**

```bash
python3 -m pytest tests/test_solar_math.py -v
```
Expected: tous les tests PASS (~18 + ~9 nouveaux = 27 tests)

- [ ] **Step 7: Commit**

```bash
git add custom_components/sunny/solar_math.py tests/test_solar_math.py
git commit -m "feat: remplacer mur-écran par obstacles 3D dans solar_math"
```

---

### Task 3: Stratégies — shadow mask + _block_all_position

**Files:**
- Modify: `custom_components/sunny/strategies.py`
- Modify: `tests/test_strategies.py`

**Interfaces:**
- Consumes: `_ray_box_intersect` from `solar_math`, `compute_window` result dict with `obstacles`
- Produces: `_build_shadow_mask(data)`, `_lit_at_cover_position(data, cover_pos)` updated, `_block_all_position(data)`, `search_cover_position` updated

- [ ] **Step 1: Adapter les tests strategies**

Dans `tests/test_strategies.py`, il faut :
1. Remplacer `screen_blocks_all` par `lit_pct: 0` dans les fixtures et tests
2. Remplacer `y_ombre` par des obstacles équivalents dans les données de test
3. Supprimer `_no_sun_data` (redondante) ou l'adapter

Remplacer les fixtures en haut du fichier (lignes 14-34) :

```python
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
```

Adapter les tests `TestLitAtCoverPosition` :
- `test_screen_blocks_all` (ligne 45-48) → remplacer `screen_blocks_all` par `lit_pct: 0` :

```python
    def test_all_shadowed(self):
        assert strategies._lit_at_cover_position(
            {"behind": False, "lit_pct": 0.0, "obstacles": []}, 100
        ) == 0.0
```

- `test_full_sun_with_wall_shadow` (ligne 83-92) → remplacer par version obstacles :

```python
    def test_full_sun_with_wall_shadow(self):
        data = _full_sun_data(d_lat=0.4, d_vert=0.3)
        lit = strategies._lit_at_cover_position(data, 100)
        assert lit == 64.0
```

- `test_screen_partial_shadow` (ligne 94-99) → remplacer par obstacle frontal :

```python
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
```

Adapter les tests `TestSearchCoverPosition` :
- `test_screen_blocks_all` (ligne 117-120) → remplacer par `lit_pct: 0` :

```python
    def test_all_shadowed(self):
        assert strategies.search_cover_position(
            {"behind": False, "lit_pct": 0.0, "obstacles": []}, 30.0
        ) == 100
```

Adapter les tests `TestBlockAllStrategy` :
- `test_screen_blocks` (ligne 180-183) → remplacer par `lit_pct: 0` :

```python
    def test_all_shadowed(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data(lit_pct=0))
        assert pos == 100
```

- `test_no_lit` (ligne 185-188) → garder, déjà correct (`_no_sun_data` returnne `lit_pct=0`)

- `test_full_sun` (ligne 190-194) → adapter, `y_ombre` n'existe plus. Avec `_block_all_position`, sans obstacle, le point lit le plus bas est à z=0 → pos=0 :

```python
    def test_full_sun(self):
        s = strategies.BlockAllStrategy()
        pos = s.compute_position(_full_sun_data())
        assert pos == 0
```

- `test_partial_sun` (ligne 196-199) → remplacer `y_ombre=0.5` par un obstacle qui crée une ombre équivalente. Un obstacle frontal à distance 2, hauteur 1.5, avec soleil à 30° donne y_ombre similaire. Mais le `_block_all_position` va utiliser la grille réelle. On peut tester avec un obstacle frontal concret :

```python
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
```

Adapter les tests `TestTemperatureGuardStrategy` :
- `test_hot_and_sunny` (ligne 265-270) → le test attend `pos == 0` (y_ombre=0). Sans obstacle, _block_all_position retourne 0 (plein soleil). Garder l'assert `pos == 0`.
- `test_hot_with_screen` (ligne 299-303) → remplacer `y_ombre=0.6` par obstacle :

```python
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
```

- [ ] **Step 2: Lancer les tests strategies — doivent échouer**

```bash
python3 -m pytest tests/test_strategies.py -v
```
Expected: certains FAIL — `_block_all_position` pas encore défini, import manquant

- [ ] **Step 3: Implémenter `_build_shadow_mask` et `_block_all_position` dans strategies.py**

Ajouter l'import en haut de `strategies.py` :

```python
import math

try:
    from .solar_math import _ray_box_intersect
except ImportError:
    from solar_math import _ray_box_intersect
```

Note : le try/except gère à la fois le contexte package HA (`from .solar_math`)
et le contexte standalone des tests (`from solar_math` via `sys.path`).

Ajouter après la fonction `_lit_at_cover_position` (avant `search_cover_position`) :

```python
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
```

- [ ] **Step 4: Remplacer `_lit_at_cover_position` — version grille**

Remplacer la fonction `_lit_at_cover_position` (lignes 17-72) :

```python
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

    mask = _build_shadow_mask(data)
    if not mask:
        return 0.0

    nx = len(mask)
    nz = len(mask[0])
    R = 100
    nz_check = max(1, int(Hw * R))
    cell_area = area / (nx * nz_check)

    # Position du bas du store (depuis le haut)
    if tilt_threshold <= 0 or tilt_threshold >= 100:
        y_cover = Hw * (1.0 - cover_pos / 100.0)
    else:
        y_cover = Hw * (1.0 - cover_pos / 100.0)

    # Hauteur du store depuis le bas : Hw - y_cover
    store_bottom_from_bottom = Hw - y_cover

    lit_area = 0.0
    for ix in range(nx):
        for iz in range(nz):
            if not mask[ix][iz]:
                continue
            z_w = (iz + 0.5) * Hw / nz_check

            if tilt_threshold <= 0 or tilt_threshold >= 100:
                if z_w >= store_bottom_from_bottom:
                    lit_area += cell_area
            elif cover_pos <= tilt_threshold:
                transmission = (cover_pos / tilt_threshold) * (slat_transmission / 100.0)
                lit_area += cell_area * transmission
            else:
                if z_w >= store_bottom_from_bottom:
                    lit_area += cell_area
                else:
                    lit_area += cell_area * (slat_transmission / 100.0)

    return (lit_area / area * 100.0) if area > 0 else 0.0
```

- [ ] **Step 5: Mettre à jour `search_cover_position` — remplacer screen_blocks_all**

Dans `search_cover_position`, ligne 78, remplacer :

```python
if data.get("behind") or data.get("screen_blocks_all") or data.get("lit_pct", 0) == 0:
```

par :

```python
if data.get("behind") or data.get("lit_pct", 0) == 0:
```

- [ ] **Step 6: Mettre à jour `BlockAllStrategy.compute_position`**

Remplacer le corps de `compute_position` (lignes 122-133) :

```python
    def compute_position(self, data: dict) -> int:
        return _block_all_position(data)
```

- [ ] **Step 7: Mettre à jour `TemperatureGuardStrategy.compute_position`**

Remplacer le bloc `if temp is not None...` (lignes 193-198) :

```python
        if temp is not None and temp >= temp_threshold and lit_pct >= lit_threshold:
            return _block_all_position(data)
```

- [ ] **Step 8: Lancer tous les tests**

```bash
python3 -m pytest tests/ -v
```
Expected: tous les 170 tests PASS

- [ ] **Step 9: Commit**

```bash
git add custom_components/sunny/strategies.py tests/test_strategies.py
git commit -m "feat: adapter les stratégies au modèle obstacles 3D"
```

---

### Task 4: Coordinator + sensor + migration + strings

**Files:**
- Modify: `custom_components/sunny/coordinator.py:82-93`
- Modify: `custom_components/sunny/sensor.py:207`
- Modify: `custom_components/sunny/__init__.py:46-50`
- Modify: `custom_components/sunny/strings.json:25-26,69-70,91-92`

**Interfaces:**
- Consumes: `compute_window(obstacles=...)`, `CONF_OBSTACLES`
- Produces: data dict with `obstacles` key, sensor attributes sans `screen_blocks_all`, migration function

- [ ] **Step 1: Mettre à jour coordinator.py**

Remplacer les lignes 82-93 dans `_async_update_data` :

```python
            obstacles = win.get("obstacles", [])
            alt = win.get("altitude", 10)
            ground_alt = win.get("ground_altitude", 208)

            try:
                data = compute_window(
                    h=h, As=As, An=orientation,
                    W=width, Hw=height, e=wall,
                    obstacles=obstacles, altitude=alt,
                    ground_altitude=ground_alt,
                )
```

Supprimer les lignes `sd = win.get("screen_distance", 0.0)` et `sh = win.get("screen_height", 1.0)`.

- [ ] **Step 2: Mettre à jour sensor.py — retirer screen_blocks_all**

Ligne 207, remplacer :

```python
            "screen_blocks_all": data.get("screen_blocks_all"),
```

par rien (supprimer la ligne).

- [ ] **Step 3: Ajouter la migration dans __init__.py**

Après `_migrate_window_ids` (ligne 43), ajouter :

```python
def _migrate_screen_to_obstacles(entry: ConfigEntry) -> dict | None:
    """Convertit screen_distance > 0 en obstacle frontal.

    Retourne les nouvelles options si une migration a eu lieu, None sinon.
    """
    windows = list(entry.options.get("windows", []))
    migrated = False

    for idx, win in enumerate(windows):
        if "obstacles" in win:
            continue
        win = dict(win)
        sd = win.pop("screen_distance", None)
        sh = win.pop("screen_height", None)
        obstacles = list(win.get("obstacles", []))
        if sd is not None and sd > 0:
            obstacles.append({
                "x1": -10000, "y1": sd, "z1": 0,
                "x2": 10000,  "y2": sd + 0.01, "z2": sh or 1.0,
            })
            migrated = True
        win["obstacles"] = obstacles
        windows[idx] = win

    if not migrated:
        return None

    new_options = dict(entry.options)
    new_options["windows"] = windows
    return new_options
```

Dans `async_setup_entry` (ligne 46-50), après l'appel à `_migrate_window_ids`, ajouter :

```python
    new_options = _migrate_screen_to_obstacles(entry)
    if new_options is not None:
        _LOGGER.info("Migration screen_distance → obstacles effectuée")
        hass.config_entries.async_update_entry(entry, options=new_options)
```

- [ ] **Step 4: Mettre à jour strings.json**

Supprimer les lignes contenant `screen_distance` et `screen_height` (lignes 25-26, 69-70, 91-92).

Ajouter dans `"step"` après la dernière étape existante :

```json
      "obstacles": {
        "title": "Obstacles de la fenêtre",
        "data": {
          "ox1": "x1 — gauche/droite début (m)",
          "oy1": "y1 — distance façade début (m)",
          "oz1": "z1 — hauteur début (m)",
          "ox2": "x2 — gauche/droite fin (m)",
          "oy2": "y2 — distance façade fin (m)",
          "oz2": "z2 — hauteur fin (m)"
        }
      }
```

Ajouter dans `"selector"` → `"action"` → `"options"` :

```json
        "obstacles": "Gérer les obstacles"
```

- [ ] **Step 5: Lancer les tests**

```bash
python3 -m pytest tests/ -v
```
Expected: 170 tests PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/sunny/coordinator.py custom_components/sunny/sensor.py custom_components/sunny/__init__.py custom_components/sunny/strings.json
git commit -m "feat: coordonnateur, capteurs, migration et traductions pour obstacles"
```

---

### Task 5: Config flow — retirer screen + ajouter gestion obstacles

**Files:**
- Modify: `custom_components/sunny/config_flow.py`

**Interfaces:**
- Consumes: `CONF_OBSTACLES`, `CONF_OBSTACLE_X1`-`Z2`, `DEFAULT_OBSTACLE_X1`-`Z2`
- Produces: `async_step_obstacles`, `async_step_add_obstacle`, `async_step_edit_obstacle`

- [ ] **Step 1: Mettre à jour les imports**

Remplacer les imports `CONF_SCREEN_DISTANCE`, `CONF_SCREEN_HEIGHT`, `DEFAULT_SCREEN_DISTANCE`, `DEFAULT_SCREEN_HEIGHT` par les constantes obstacles :

```python
from .const import (
    ...
    CONF_OBSTACLES,
    CONF_OBSTACLE_X1,
    CONF_OBSTACLE_Y1,
    CONF_OBSTACLE_Z1,
    CONF_OBSTACLE_X2,
    CONF_OBSTACLE_Y2,
    CONF_OBSTACLE_Z2,
    DEFAULT_OBSTACLE_X1,
    DEFAULT_OBSTACLE_Y1,
    DEFAULT_OBSTACLE_Z1,
    DEFAULT_OBSTACLE_X2,
    DEFAULT_OBSTACLE_Y2,
    DEFAULT_OBSTACLE_Z2,
    ...
)
```

- [ ] **Step 2: Retirer les champs screen de `_build_window_schema`**

Supprimer les lignes 104-107 (champs `CONF_SCREEN_DISTANCE` et `CONF_SCREEN_HEIGHT`).

Et retirer `DEFAULT_SCREEN_DISTANCE`, `DEFAULT_SCREEN_HEIGHT` de la liste d'imports si pas déjà fait.

- [ ] **Step 3: Ajouter l'action `obstacles` dans `async_step_init`**

Dans `async_step_init`, après le `elif action == "position_threshold":` (ligne 289), ajouter :

```python
            elif action == "obstacles" and window_name is not None:
                self._editing = int(window_name)
                return await self.async_step_obstacles()
```

Dans la construction du schéma (lignes 300-303), ajouter `"obstacles"` à la liste `vol.In` :

```python
            vol.Required("action"): vol.In(["edit", "delete", "add", "weather", "refresh", "position_threshold", "obstacles", "done"]),
```

- [ ] **Step 4: Ajouter `_build_obstacle_schema`**

Ajouter une fonction helper avant la classe `SunnyOptionsFlow` :

```python
def _build_obstacle_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    if defaults is None:
        defaults = {}
    return vol.Schema({
        vol.Required(CONF_OBSTACLE_X1, default=defaults.get(CONF_OBSTACLE_X1, DEFAULT_OBSTACLE_X1)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Y1, default=defaults.get(CONF_OBSTACLE_Y1, DEFAULT_OBSTACLE_Y1)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Z1, default=defaults.get(CONF_OBSTACLE_Z1, DEFAULT_OBSTACLE_Z1)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_X2, default=defaults.get(CONF_OBSTACLE_X2, DEFAULT_OBSTACLE_X2)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Y2, default=defaults.get(CONF_OBSTACLE_Y2, DEFAULT_OBSTACLE_Y2)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Z2, default=defaults.get(CONF_OBSTACLE_Z2, DEFAULT_OBSTACLE_Z2)):
            vol.All(vol.Coerce(float)),
    })
```

- [ ] **Step 5: Ajouter les steps obstacles dans `SunnyOptionsFlow`**

Ajouter ces méthodes dans `SunnyOptionsFlow` :

```python
    async def async_step_obstacles(self, user_input: dict[str, Any] | None = None):
        """Liste des obstacles d'une fenêtre avec actions ajouter/modifier/supprimer."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_obstacle()
            elif action == "back":
                return await self.async_step_init()
            elif action is not None:
                # "edit_N" ou "delete_N"
                parts = action.split("_", 1)
                if len(parts) == 2:
                    idx = int(parts[1])
                    windows = self.data.get(CONF_WINDOWS, [])
                    if self._editing is not None and self._editing < len(windows):
                        win = windows[self._editing]
                        obstacles = list(win.get(CONF_OBSTACLES, []))
                        if parts[0] == "edit" and 0 <= idx < len(obstacles):
                            self._obstacle_editing = idx
                            return await self.async_step_edit_obstacle()
                        elif parts[0] == "delete" and 0 <= idx < len(obstacles):
                            obstacles.pop(idx)
                            win = dict(win)
                            win[CONF_OBSTACLES] = obstacles
                            windows[self._editing] = win
                            self.data[CONF_WINDOWS] = windows
                return await self.async_step_obstacles()

        windows = self.data.get(CONF_WINDOWS, [])
        obstacles = []
        if self._editing is not None and self._editing < len(windows):
            obstacles = windows[self._editing].get(CONF_OBSTACLES, [])

        options = []
        for i, obs in enumerate(obstacles):
            label = f"Obstacle {i+1} : ({obs.get(CONF_OBSTACLE_X1,0)},{obs.get(CONF_OBSTACLE_Y1,0)},{obs.get(CONF_OBSTACLE_Z1,0)})→({obs.get(CONF_OBSTACLE_X2,0)},{obs.get(CONF_OBSTACLE_Y2,0)},{obs.get(CONF_OBSTACLE_Z2,0)})"
            options.extend([
                {"label": f"✏️ {label}", "value": f"edit_{i}"},
                {"label": f"🗑️ Supprimer", "value": f"delete_{i}"},
            ])

        schema = vol.Schema({
            vol.Required("action"): vol.In(
                {o["value"]: o["label"] for o in options} | {"add": "+ Ajouter un obstacle", "back": "← Retour"}
            ),
        })

        return self.async_show_form(step_id="obstacles", data_schema=schema)

    async def async_step_add_obstacle(self, user_input: dict[str, Any] | None = None):
        """Formulaire d'ajout d'un obstacle."""
        if user_input is not None:
            windows = self.data.get(CONF_WINDOWS, [])
            if self._editing is not None and self._editing < len(windows):
                win = dict(windows[self._editing])
                obstacles = list(win.get(CONF_OBSTACLES, []))
                obstacles.append({
                    CONF_OBSTACLE_X1: user_input[CONF_OBSTACLE_X1],
                    CONF_OBSTACLE_Y1: user_input[CONF_OBSTACLE_Y1],
                    CONF_OBSTACLE_Z1: user_input[CONF_OBSTACLE_Z1],
                    CONF_OBSTACLE_X2: user_input[CONF_OBSTACLE_X2],
                    CONF_OBSTACLE_Y2: user_input[CONF_OBSTACLE_Y2],
                    CONF_OBSTACLE_Z2: user_input[CONF_OBSTACLE_Z2],
                })
                win[CONF_OBSTACLES] = obstacles
                windows[self._editing] = win
                self.data[CONF_WINDOWS] = windows
            return await self.async_step_obstacles()

        return self.async_show_form(
            step_id="add_obstacle",
            data_schema=_build_obstacle_schema(),
        )

    async def async_step_edit_obstacle(self, user_input: dict[str, Any] | None = None):
        """Formulaire d'édition d'un obstacle existant."""
        if user_input is not None:
            windows = self.data.get(CONF_WINDOWS, [])
            if self._editing is not None and self._editing < len(windows):
                win = dict(windows[self._editing])
                obstacles = list(win.get(CONF_OBSTACLES, []))
                idx = getattr(self, "_obstacle_editing", -1)
                if 0 <= idx < len(obstacles):
                    obstacles[idx] = {
                        CONF_OBSTACLE_X1: user_input[CONF_OBSTACLE_X1],
                        CONF_OBSTACLE_Y1: user_input[CONF_OBSTACLE_Y1],
                        CONF_OBSTACLE_Z1: user_input[CONF_OBSTACLE_Z1],
                        CONF_OBSTACLE_X2: user_input[CONF_OBSTACLE_X2],
                        CONF_OBSTACLE_Y2: user_input[CONF_OBSTACLE_Y2],
                        CONF_OBSTACLE_Z2: user_input[CONF_OBSTACLE_Z2],
                    }
                    win[CONF_OBSTACLES] = obstacles
                    windows[self._editing] = win
                    self.data[CONF_WINDOWS] = windows
            self._obstacle_editing = -1
            return await self.async_step_obstacles()

        windows = self.data.get(CONF_WINDOWS, [])
        current = {}
        if self._editing is not None and self._editing < len(windows):
            obstacles = windows[self._editing].get(CONF_OBSTACLES, [])
            idx = getattr(self, "_obstacle_editing", -1)
            if 0 <= idx < len(obstacles):
                current = obstacles[idx]

        return self.async_show_form(
            step_id="edit_obstacle",
            data_schema=_build_obstacle_schema(current),
        )
```

- [ ] **Step 6: Ajouter `_obstacle_editing` dans `__init__`**

Dans `SunnyOptionsFlow.__init__`, après `self._editing: int | None = None`, ajouter :

```python
        self._obstacle_editing: int = -1
```

- [ ] **Step 7: Lancer les tests**

```bash
python3 -m pytest tests/ -v
```
Expected: 170 tests PASS (les tests n'importent pas HA, donc pas de tests config_flow)

- [ ] **Step 8: Commit**

```bash
git add custom_components/sunny/config_flow.py
git commit -m "feat: gestion des obstacles dans le config flow"
```

---

### Task 6: Vérification finale

- [ ] **Step 1: Lancer tous les tests**

```bash
python3 -m pytest tests/ -v
```
Expected: tous les 170 tests PASS

- [ ] **Step 2: Vérifier qu'il n'y a plus de références à screen_distance/screen_height/y_ombre/screen_blocks_all**

```bash
grep -rn "screen_distance\|screen_height\|screen_blocks_all\|y_ombre" custom_components/sunny/
```
Expected: aucune occurrence (sauf peut-être dans la migration de __init__.py qui référence explicitement les anciens champs pour les convertir)

- [ ] **Step 3: Commit final si nécessaire**

```bash
git add -A && git diff --cached --stat
```