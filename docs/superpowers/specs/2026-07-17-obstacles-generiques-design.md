# Obstacles génériques 3D

**Date :** 2026-07-17
**Statut :** design validé, en attente d'implémentation

## Contexte

L'intégration Sunny modélise actuellement un seul type d'obstacle : un mur-écran
infini horizontalement (`screen_distance` / `screen_height`). Ce modèle ne couvre
pas le cas d'une aile de bâtiment qui projette de l'ombre latéralement sur la
fenêtre, ni d'autres types d'obstructions 3D.

On remplace le mur-écran unique par un système d'obstacles 3D génériques, chaque
obstacle étant une boîte alignée définie par 2 coins opposés.

## 1. Modèle de données

### Coordonnées locales à la fenêtre

| Axe | Signification | Positif vers |
|-----|--------------|-------------|
| `x` | gauche / droite le long de la façade | droite |
| `y` | distance depuis la façade | extérieur |
| `z` | hauteur depuis le bas de la fenêtre | haut |

Origine `(0, 0, 0)` = coin bas-gauche de la fenêtre, sur le plan de la façade.

### Obstacle = boîte 3D alignée, définie par 2 coins opposés

```json
{"x1": -10, "y1": 0, "z1": 0, "x2": 0.5, "y2": 3, "z2": 6}
```

| Param | Signification |
|-------|--------------|
| `x1, x2` | positions gauche/droite (m) |
| `y1, y2` | distances depuis la façade (m) |
| `z1, z2` | hauteurs depuis le bas de la fenêtre (m) |

La boîte occupe `[min(x1,x2), max(x1,x2)] × [min(y1,y2), max(y1,y2)] × [min(z1,z2), max(z1,z2)]`.
Les coins peuvent être donnés dans n'importe quel ordre — `min`/`max` normalise.

La représentation `(x1,y1,z1), (x2,y2,z2)` laisse la porte ouverte à des boîtes
orientées dans le futur (les 2 points seraient alors les coins d'une boîte en
rotation).

### Exemples

**Aile gauche**
```json
{"x1": -10, "y1": 0, "z1": 0, "x2": 0.5, "y2": 3, "z2": 6}
```
→ boîte de x=-10 à x=0.5, y=0 à y=3, z=0 à z=6

**Mur en face (équivalent ancien écran)**
```json
{"x1": -10000, "y1": 5, "z1": 0, "x2": 10000, "y2": 5.01, "z2": 3}
```
→ plan vertical infini horizontalement, à 5m, hauteur 3m

### Stockage dans la config

Chaque fenêtre a un champ `obstacles` (liste, vide par défaut) :

```python
CONF_OBSTACLES = "obstacles"
DEFAULT_OBSTACLES: list[dict] = []
```

Les champs `screen_distance` et `screen_height` sont **supprimés**.

### Constantes

```python
CONF_OBSTACLES = "obstacles"
CONF_OBSTACLE_X1 = "ox1"
CONF_OBSTACLE_Y1 = "oy1"
CONF_OBSTACLE_Z1 = "oz1"
CONF_OBSTACLE_X2 = "ox2"
CONF_OBSTACLE_Y2 = "oy2"
CONF_OBSTACLE_Z2 = "oz2"

DEFAULT_OBSTACLE_X1 = 0.0
DEFAULT_OBSTACLE_Y1 = 0.0
DEFAULT_OBSTACLE_Z1 = 0.0
DEFAULT_OBSTACLE_X2 = 1.0
DEFAULT_OBSTACLE_Y2 = 1.0
DEFAULT_OBSTACLE_Z2 = 1.0
```

### Migration automatique

Au démarrage (`__init__.py`), si une fenêtre a `screen_distance > 0` :

```python
obstacle_frontal = {
    "x1": -10000, "y1": screen_distance, "z1": 0,
    "x2": 10000,  "y2": screen_distance + 0.01, "z2": screen_height,
}
```

Les anciens champs `screen_distance` et `screen_height` sont retirés de la config
sauvegardée via `hass.config_entries.async_update_entry()`. La migration est
idempotente (détecte la présence d'`obstacles` pour éviter une double conversion).

## 2. Calcul des ombres (`solar_math.py`)

### Nouvelle signature

```python
def compute_window(
    h: float, As: float, An: float,
    W: float, Hw: float,
    e: float = 0.25,
    obstacles: list[dict] | None = None,
    altitude: float = 0.0,
    ground_altitude: float = 0.0,
) -> dict:
```

`D` et `Hm` sont retirés, remplacés par `obstacles`.

### Algorithme

1. Dip d'horizon, γ, behind → inchangé
2. Si `behind=True` → retour immédiat (inchangé)
3. Calcul de θ, hp, d_lat, d_vert (ombres d'embrasure révélées) → inchangé
4. **Étape obstacles** :
   - Résolution proportionnelle à la taille : `nx = max(1, int(W × R))`, `nz = max(1, int(Hw × R))` avec `R = 100` pts/m
   - Pour chaque cellule `(ix, iz)` → point central `(x_w, 0, z_w)`
   - Rayon vers le soleil : direction `(sin(γ)·cos(h), cos(γ)·cos(h), sin(h))`
   - Intersection rayon-boîte (slab method) contre chaque obstacle
   - Si le rayon intersecte un obstacle → point à l'ombre
5. Zone éclairée = points non bloqués × surface d'une cellule
6. `lit_pct` et `lit_area_m2` calculés comme avant

### Intersection rayon-boîte (slab method)

Pour un rayon `P + t·D` et une boîte normalisée `[xmin, xmax] × [ymin, ymax] × [zmin, zmax]` :

```
tmin = max(
    (xmin - Px)/Dx si Dx>0 sinon (xmax - Px)/Dx,
    (ymin - Py)/Dy si Dy>0 sinon (ymax - Py)/Dy,
    (zmin - Pz)/Dz si Dz>0 sinon (zmax - Pz)/Dz,
)
tmax = min(
    (xmax - Px)/Dx si Dx>0 sinon (xmin - Px)/Dx,
    (ymax - Py)/Dy si Dy>0 sinon (ymin - Py)/Dy,
    (zmax - Pz)/Dz si Dz>0 sinon (zmin - Pz)/Dz,
)
intersection si tmin < tmax et tmax > 0
```

Gérer `Dx == 0`, `Dy == 0`, `Dz == 0` (rayon parallèle à un plan de la boîte) :
si `Px` est hors de `[xmin, xmax]` → pas d'intersection.

### Sortie

Les champs `y_ombre` et `screen_blocks_all` sont **supprimés** du dict résultat.
Tous les autres champs restent inchangés.

Nouveau champ ajouté au dict pour les stratégies :
- `obstacles` : la liste brute des obstacles (pour `_lit_at_cover_position`)

## 3. Stratégies (`strategies.py`)

### `_lit_at_cover_position(data, cover_pos)` — repensé

Actuellement basée sur `y_ombre` (bande d'ombre depuis le bas) et `d_vert`
(bande depuis le haut). Avec les obstacles génériques, l'ombre n'est plus une
simple bande horizontale.

**Nouvelle approche :** discrétisation identique à `compute_window()`.

1. Extraire `W`, `Hw`, `d_lat`, `d_vert`, `obstacles`, `gamma`, `hp` du dict `data`
2. Construire la grille `nx × nz` (même résolution `R=100`)
3. Pour chaque point de la grille :
   - Si dans l'ombre d'embrasure (d_lat / d_vert) → point bloqué
   - Si rayon vers le soleil intersecte un obstacle → point bloqué
   - Sinon : appliquer le modèle store (tilt / levée) comme actuellement
4. Retourner le pourcentage moyen

Le point 3 bénéficie d'une optimisation : pré-calculer `shadow_mask[nx][nz]`
(booléen) une seule fois, puis l'appliquer pour chaque appel à
`_lit_at_cover_position` dans la boucle de `search_cover_position`.

### `search_cover_position(data, target_pct)`

Remplacer `data.get("screen_blocks_all")` par `data.get("lit_pct", 0) == 0`.

Les conditions deviennent :
```python
if data.get("behind") or data.get("lit_pct", 0) == 0:
    return 100
```

### `BlockAllStrategy`

**Avant :** `pos = 100 * y_ombre / Hw`

**Après :** `return search_cover_position(data, 0.0)`

### `TemperatureGuardStrategy`

**Avant :** calcul manuel `y_ombre / Hw`

**Après :** `return search_cover_position(data, 0.0)` quand chaud + soleil,
`return 100` sinon.

### Autres stratégies

`WinterPassiveStrategy`, `ProportionalStrategy`, `ThresholdStrategy`,
`TargetIlluminationStrategy` utilisent déjà `lit_pct` ou `search_cover_position()`
→ compatibles sans changement.

## 4. Config flow (`config_flow.py`)

### Suppression des champs écran

Retirer `CONF_SCREEN_DISTANCE` et `CONF_SCREEN_HEIGHT` de `_build_window_schema()`.

### Sous-menu obstacles

Dans `SunnyOptionsFlow.async_step_init()`, ajouter `"obstacles"` aux actions.
L'action `obstacles` + sélection d'une fenêtre mène à `async_step_obstacles()`.

```
async_step_obstacles(window_idx) :
  → liste des obstacles du window_idx avec :
    - obstacle N : boutons "edit" / "delete"
    - "+ Ajouter un obstacle"
    - "← Retour"
```

```
async_step_add_obstacle() :
  → formulaire 6 champs : x1, y1, z1, x2, y2, z2
  → validation : nombres valides, pas de contrainte min/max
  → retour à async_step_obstacles
```

```
async_step_edit_obstacle(obstacle_idx) :
  → formulaire pré-rempli avec les valeurs actuelles
  → retour à async_step_obstacles
```

### Ranges des champs dans le formulaire

| Champ | Range | Défaut |
|-------|-------|--------|
| `x1` | -100 à 100 | 0 |
| `y1` | 0 à 50 | 0 |
| `z1` | 0 à 50 | 0 |
| `x2` | -100 à 100 | 1 |
| `y2` | 0 à 50 | 1 |
| `z2` | 0 à 50 | 1 |

### `strings.json` — traductions à ajouter

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

```json
"selector": {
    "action": {
        "options": {
            "obstacles": "Gérer les obstacles"
        }
    }
}
```

## 5. Simulateur (`simulateur_ensoleillement_fenetre.html`)

- Remplacer `D` / `Hm` par une liste d'obstacles éditable
- Chaque obstacle : 6 inputs numériques `(x1,y1,z1,x2,y2,z2)` + bouton supprimer
- Bouton « + Ajouter un obstacle »
- Moteur JS : même algorithme (discrétisation + intersection rayon-boîte)
- Visualisation plan/coupe : afficher les boîtes 3D projetées

## 6. Fichiers impactés

| Fichier | Changement |
|---------|-----------|
| `const.py` | Remplacer `CONF_SCREEN_*` / `DEFAULT_SCREEN_*` par `CONF_OBSTACLES` + constantes obstacle |
| `solar_math.py` | `compute_window()` : remplacer `D, Hm` par `obstacles`, ajouter grille + ray-box, retirer `y_ombre`/`screen_blocks_all`, ajouter `obstacles` au résultat |
| `strategies.py` | `_lit_at_cover_position()` repensé via grille + shadow_mask, remplacer `screen_blocks_all` par `lit_pct == 0`, `BlockAllStrategy`/`TemperatureGuardStrategy` via `search_cover_position` |
| `coordinator.py` | Lire `obstacles` au lieu de `sd, sh`, passer à `compute_window()`, ajouter `obstacles` au dict `data` |
| `config_flow.py` | Retirer champs écran de `_build_window_schema()`, ajouter sous-menu obstacles (3 steps) |
| `__init__.py` | Migration auto `screen_distance > 0` → `obstacles` |
| `sensor.py` | Retirer `screen_blocks_all` des `extra_state_attributes` |
| `strings.json` | Retirer les traductions `screen_distance`/`screen_height`, ajouter celles des obstacles |
| `simulateur_ensoleillement_fenetre.html` | Remplacer mur-écran par système d'obstacles |
| `tests/test_solar_math.py` | Nouveaux tests obstacles, supprimer tests `screen_*` |
| `tests/test_strategies.py` | Adapter données de test (obstacles au lieu de y_ombre/screen_blocks_all) |

## 7. Plan de test

### Nouveaux tests `test_solar_math.py`

- `test_no_obstacles_full_sun` — liste vide, 100% éclairé
- `test_single_frontal_wall` — équivalent à l'ancien mur-écran via obstacle `(x1=-10000, x2=10000, y1=D, y2=D+0.01, z1=0, z2=Hm)`
- `test_single_lateral_wing_left` — aile à gauche, γ < 0 → ombre partielle
- `test_single_lateral_wing_right` — aile à droite, γ > 0 → ombre partielle
- `test_lateral_wing_behind` — γ opposé à l'aile → pas d'ombre
- `test_multiple_obstacles_combined` — mur frontal + aile latérale, ombres cumulées
- `test_obstacle_discretization_resolution` — nx/nz proportionnel à W/Hw
- `test_migration_screen_to_obstacle` — screen_distance > 0 converti correctement

### Tests à adapter `test_strategies.py`

- Fixtures : remplacer `y_ombre`/`screen_blocks_all` par des données `obstacles`
  qui produisent le même `lit_pct`
- Tests `BlockAll` : le résultat doit être identique via `search_cover_position(data, 0.0)`
- Tests `TemperatureGuard` : idem

### Tests à supprimer

- Tests spécifiques à `screen_distance`/`screen_height`/`y_ombre` dans `test_solar_math.py`