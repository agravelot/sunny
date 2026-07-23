# Stratégie lux_target — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une stratégie de régulation par capteur lux intérieur (seuil + hystérésis + pas fixe) avec sélection de capteurs par liste explicite ou zone HA.

**Architecture:** Stratégie stateless `LuxTargetStrategy` dans `strategies.py`. Le coordinateur lit l'état du cover et des capteurs, vérifie la fraîcheur (`sensor.last_updated > cover.last_changed`), agrège les valeurs fraîches, puis délègue le calcul à la stratégie. Le switch existant applique la position comme pour les autres stratégies.

**Tech Stack:** Python, Home Assistant DataUpdateCoordinator, voluptuous, entity_registry

## Global Constraints

- Tout en français (code, logs, UI)
- Stratégie pure (pas d'état interne)
- `sensor.last_updated > cover.last_changed` avant tout recalcul
- Capteurs explicites (`lux_sensors`) prioritaires sur zone HA (`lux_area_id`)
- Si aucun capteur frais → position inchangée
- Départ à 100% (ouvert), le switch gère l'application incrémentale
- Tests unitaires sans Home Assistant

## Design Doc

`docs/superpowers/specs/2026-07-19-strategie-lux-target-design.md`

---

### Task 1: Nouvelles constantes

**Files:**
- Modify: `custom_components/sunny/const.py`

**Interfaces:**
- Produces: `CONF_LUX_SENSORS`, `CONF_LUX_AREA_ID`, `CONF_LUX_HIGH`, `CONF_LUX_LOW`, `CONF_LUX_STEP`, `DEFAULT_LUX_HIGH`, `DEFAULT_LUX_LOW`, `DEFAULT_LUX_STEP`

- [ ] **Step 1: Ajouter les constantes dans const.py**

Ajouter après la ligne `CONF_TARGET_ILLUMINATION = "target_illumination"` :

```python
CONF_LUX_SENSORS = "lux_sensors"
CONF_LUX_AREA_ID = "lux_area_id"
CONF_LUX_HIGH = "lux_high"
CONF_LUX_LOW = "lux_low"
CONF_LUX_STEP = "lux_step"
```

Ajouter après la ligne `DEFAULT_TARGET_ILLUMINATION = 30.0` :

```python
DEFAULT_LUX_HIGH = 5000.0
DEFAULT_LUX_LOW = 3000.0
DEFAULT_LUX_STEP = 10
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/sunny/const.py
git commit -m "add lux_target constants"
```

---

### Task 2: Stratégie LuxTargetStrategy

**Files:**
- Modify: `custom_components/sunny/strategies.py:307-321`

**Interfaces:**
- Produces: `LuxTargetStrategy` class, registered in `STRATEGIES` dict and `STRATEGY_OPTIONS`
- Consumes: `BaseStrategy` (existing)

- [ ] **Step 1: Ajouter la classe LuxTargetStrategy**

Avant le bloc `# ---------------------------------------------------------------------------\n# Registre`, après la classe `AlwaysOpenStrategy`, ajouter :

```python
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
```

- [ ] **Step 2: Enregistrer la stratégie dans les dictionnaires**

Dans `STRATEGIES`, ajouter après `"always_open": AlwaysOpenStrategy(),` :

```python
    "lux_target": LuxTargetStrategy(),
```

Dans `STRATEGY_OPTIONS`, la compréhension `{k: v.label for k, v in STRATEGIES.items()}` inclut automatiquement la nouvelle entrée. Vérifier que la ligne 323 est bien :

```python
STRATEGY_OPTIONS = {k: v.label for k, v in STRATEGIES.items()}
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/sunny/strategies.py
git commit -m "add LuxTargetStrategy for lux-based regulation"
```

---

### Task 3: Coordinateur — lecture capteurs et fraîcheur

**Files:**
- Modify: `custom_components/sunny/coordinator.py`

**Interfaces:**
- Consumes: `CONF_LUX_*`, `DEFAULT_LUX_*` from `const.py`, `LuxTargetStrategy` from `strategies.py`
- Modifies: `_async_update_data` to handle lux_target windows

- [ ] **Step 1: Ajouter les imports**

Après `from .const import (` ajouter les nouvelles constantes :

```python
    CONF_LUX_SENSORS,
    CONF_LUX_AREA_ID,
    CONF_LUX_HIGH,
    CONF_LUX_LOW,
    CONF_LUX_STEP,
    DEFAULT_LUX_HIGH,
    DEFAULT_LUX_LOW,
    DEFAULT_LUX_STEP,
```

Ajouter l'import de l'entity registry en haut du fichier :

```python
from homeassistant.helpers import entity_registry as er
```

- [ ] **Step 2: Ajouter la méthode helper `_resolve_lux_sensors`**

Dans la classe `SunnyCoordinator`, avant `_async_update_data`, ajouter :

```python
    def _resolve_lux_sensors(self, win: dict) -> list[str]:
        """Résout la liste des capteurs lux pour une fenêtre.

        Priorité : lux_sensors (explicite) > lux_area_id (découverte zone HA).
        """
        explicit = win.get("lux_sensors", [])
        if explicit:
            return [e for e in explicit if isinstance(e, str) and e]

        area_id = win.get("lux_area_id")
        if not area_id:
            return []

        ent_reg = er.async_get(self.hass)
        sensors = []
        for entity in ent_reg.entities.values():
            if (
                entity.domain == "sensor"
                and entity.area_id == area_id
                and entity.device_class == "illuminance"
                and not entity.disabled
            ):
                sensors.append(entity.entity_id)
        return sensors
```

- [ ] **Step 3: Ajouter la méthode helper `_compute_lux_target_position`**

Dans la classe `SunnyCoordinator`, après `_resolve_lux_sensors`, ajouter :

```python
    def _compute_lux_target_position(self, win: dict, strategy) -> int:
        """Calcule la position pour une fenêtre en stratégie lux_target.

        Retourne la position inchangée si aucun capteur frais.
        """
        cover_entity = win.get("cover_entity", "")
        cover_state = self.hass.states.get(cover_entity)
        current_position = 100
        cover_last_changed = None
        if cover_state is not None:
            pos = cover_state.attributes.get("current_position")
            if pos is not None:
                try:
                    current_position = int(float(pos))
                except (ValueError, TypeError):
                    pass
            cover_last_changed = cover_state.last_changed

        sensor_ids = self._resolve_lux_sensors(win)
        if not sensor_ids:
            _LOGGER.warning(
                "Aucun capteur lux trouvé pour la fenêtre '%s' (lux_sensors=%s, lux_area_id=%s)",
                win.get("name", "Inconnue"),
                win.get("lux_sensors", []),
                win.get("lux_area_id"),
            )
            return current_position

        fresh_values = []
        stale_count = 0
        for sid in sensor_ids:
            sensor_state = self.hass.states.get(sid)
            if sensor_state is None:
                _LOGGER.debug("Capteur lux '%s' introuvable", sid)
                continue
            if cover_last_changed is not None and sensor_state.last_updated <= cover_last_changed:
                stale_count += 1
                _LOGGER.debug(
                    "Capteur lux '%s' stale (last_updated=%s <= cover.last_changed=%s)",
                    sid, sensor_state.last_updated, cover_last_changed,
                )
                continue
            try:
                val = float(sensor_state.state)
                fresh_values.append(val)
                _LOGGER.debug(
                    "Capteur lux '%s' frais : %s lx (last_updated=%s)",
                    sid, val, sensor_state.last_updated,
                )
            except (ValueError, TypeError):
                _LOGGER.debug("Capteur lux '%s' valeur non numérique: %s", sid, sensor_state.state)

        if not fresh_values:
            _LOGGER.info(
                "Aucun capteur frais pour la fenêtre '%s' (%d stale sur %d), position inchangée à %d",
                win.get("name", "Inconnue"), stale_count, len(sensor_ids), current_position,
            )
            return current_position

        lux_value = sum(fresh_values) / len(fresh_values)
        _LOGGER.debug(
            "Lux agrégé pour '%s': %.0f lx (moyenne de %d capteurs)",
            win.get("name", "Inconnue"), lux_value, len(fresh_values),
        )

        data = {
            "lux_value": lux_value,
            "current_position": current_position,
            "lux_high": win.get("lux_high", DEFAULT_LUX_HIGH),
            "lux_low": win.get("lux_low", DEFAULT_LUX_LOW),
            "lux_step": win.get("lux_step", DEFAULT_LUX_STEP),
        }
        new_position = strategy.compute_position(data)
        if new_position != current_position:
            _LOGGER.info(
                "Lux target '%s': lux=%.0f lx, position %d → %d",
                win.get("name", "Inconnue"), lux_value, current_position, new_position,
            )
        return new_position
```

- [ ] **Step 4: Modifier `_async_update_data` pour les fenêtres lux_target**

Dans la boucle `for idx, win in enumerate(windows):`, après la ligne `strategy_name = win.get("strategy", "block_all")` et avant `strategy = get_strategy(strategy_name)`, ajouter le traitement spécial pour lux_target. Remplacer le bloc :

```python
            strategy_name = win.get("strategy", "block_all")
            strategy = get_strategy(strategy_name)
            data["strategy"] = strategy_name
            data["desired_position"] = strategy.compute_position(data)
```

par :

```python
            strategy_name = win.get("strategy", "block_all")
            strategy = get_strategy(strategy_name)
            data["strategy"] = strategy_name
            if strategy_name == "lux_target":
                data["desired_position"] = self._compute_lux_target_position(win, strategy)
            else:
                data["desired_position"] = strategy.compute_position(data)
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/sunny/coordinator.py
git commit -m "add lux sensor resolution and freshness check in coordinator"
```

---

### Task 4: Config flow — champs lux_target

**Files:**
- Modify: `custom_components/sunny/config_flow.py`

**Interfaces:**
- Consumes: `CONF_LUX_*`, `DEFAULT_LUX_*` from `const.py`
- Modifies: `_build_window_schema` to add lux fields

- [ ] **Step 1: Mettre à jour les imports**

Dans l'import depuis `.const`, ajouter les nouvelles constantes :

```python
    CONF_LUX_SENSORS,
    CONF_LUX_AREA_ID,
    CONF_LUX_HIGH,
    CONF_LUX_LOW,
    CONF_LUX_STEP,
    DEFAULT_LUX_HIGH,
    DEFAULT_LUX_LOW,
    DEFAULT_LUX_STEP,
```

Dans l'import de `homeassistant.helpers.selector`, ajouter :

```python
from homeassistant.helpers.selector import (
    AreaSelector,
    AreaSelectorConfig,
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    EntitySelectorConfig,
)
```

- [ ] **Step 2: Ajouter les champs lux dans `_build_window_schema`**

Dans `_build_window_schema`, après le bloc `zone_entity`, ajouter les champs lux :

```python
        vol.Optional(CONF_LUX_SENSORS, default=defaults.get(CONF_LUX_SENSORS, [])):
            EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True)),
        vol.Optional(CONF_LUX_AREA_ID, default=defaults.get(CONF_LUX_AREA_ID)):
            AreaSelector(AreaSelectorConfig()),
        vol.Optional(CONF_LUX_HIGH, default=defaults.get(CONF_LUX_HIGH, DEFAULT_LUX_HIGH)):
            vol.All(vol.Coerce(float), vol.Range(min=100, max=100000)),
        vol.Optional(CONF_LUX_LOW, default=defaults.get(CONF_LUX_LOW, DEFAULT_LUX_LOW)):
            vol.All(vol.Coerce(float), vol.Range(min=100, max=100000)),
        vol.Optional(CONF_LUX_STEP, default=defaults.get(CONF_LUX_STEP, DEFAULT_LUX_STEP)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/sunny/config_flow.py
git commit -m "add lux_target fields to config flow"
```

---

### Task 5: Traductions strings.json

**Files:**
- Modify: `custom_components/sunny/strings.json`

**Interfaces:**
- Produces: Labels UI pour les nouveaux champs

- [ ] **Step 1: Ajouter les traductions dans strings.json**

Dans chaque bloc `data` (step `window`, `edit_window`, `add_window`), ajouter avant la dernière ligne (avant `"zone_entity"` dans `window`/`edit_window`, avant `"target_illumination"` dans `add_window`) :

```
          "lux_sensors": "Capteurs lux",
          "lux_area_id": "Zone HA (alternative aux capteurs)",
          "lux_high": "Seuil haut lux (lx)",
          "lux_low": "Seuil bas lux (lx)",
          "lux_step": "Pas d'ajustement (%)"
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/sunny/strings.json
git commit -m "add lux_target UI translations"
```

---

### Task 6: Tests unitaires

**Files:**
- Modify: `tests/test_strategies.py`

**Interfaces:**
- Consumes: `LuxTargetStrategy` from `strategies`

- [ ] **Step 1: Ajouter la classe de tests LuxTargetStrategy**

Avant la classe `TestRegistry` (ligne 388), ajouter :

```python
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
```

- [ ] **Step 2: Mettre à jour le test du registre**

Dans `TestRegistry.test_strategies_dict`, mettre à jour le `assert len(strategies.STRATEGIES) == 9` en `== 10` et ajouter la vérification :

```python
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
```

- [ ] **Step 3: Exécuter les tests et vérifier**

```bash
python3 -m pytest tests/test_strategies.py -v
```

Expected: 14 nouveaux tests + 52 existants = 66 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_strategies.py
git commit -m "add LuxTargetStrategy unit tests"
```

---

### Task 7: Vérification globale

**Files:**
- None (read-only check)

- [ ] **Step 1: Lancer tous les tests**

```bash
python3 -m pytest tests/ -v
```

Expected: 88 tests existants + 14 nouveaux = ~102 PASS

- [ ] **Step 2: Vérifier l'import du module stratégies**

```bash
python3 -c "import sys; sys.path.insert(0, 'custom_components/sunny'); import strategies; s = strategies.LuxTargetStrategy(); print(s.name, s.label)"
```

Expected: `lux_target Cible lux intérieur (capteur)`

- [ ] **Step 3: Commit final si modifications résiduelles**

```bash
git status
```