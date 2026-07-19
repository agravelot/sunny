# Seuil de tolérance de position — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un seuil global configurable (3% par défaut) pour éviter d'envoyer des commandes `set_cover_position` quand la position désirée diffère de moins de X% de la position réelle du cover, sauf pour 0 et 100 qui sont toujours appliqués.

**Architecture:** Le seuil est stocké dans `entry.options["position_threshold"]`, lu par `SunnyAutoControlSwitch._should_apply()` qui compare la position désirée avec l'état réel du cover via `hass.states.get()`. La config est exposée dans l'OptionsFlow comme une nouvelle étape (même pattern que `refresh_interval`).

**Tech Stack:** Python, Home Assistant (states.get, NumberSelector, OptionsFlow), pytest

## Global Constraints

- Tout code et UI en français
- Tests sans import HA (mock `hass.states.get`)
- Le simulateur HTML n'est pas concerné
- Ne pas casser les 88 tests existants

---

### Task 1: Ajouter les constantes

**Files:**
- Modify: `custom_components/sunny/const.py`

**Interfaces:**
- Produces: `CONF_POSITION_THRESHOLD = "position_threshold"`, `DEFAULT_POSITION_THRESHOLD = 3`

- [ ] **Step 1: Ajouter les deux constantes dans const.py**

After `CONF_REFRESH_INTERVAL = "refresh_interval"` (line 20), insert:

```python
CONF_POSITION_THRESHOLD = "position_threshold"
```

After `DEFAULT_REFRESH_INTERVAL = 5` (line 43), insert:

```python
DEFAULT_POSITION_THRESHOLD = 3
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/sunny/const.py
git commit -m "add position threshold constants"
```

---

### Task 2: Écrire les tests pour `_should_apply`

**Files:**
- Modify: `tests/test_switch.py`

**Interfaces:**
- Consumes: `DEFAULT_POSITION_THRESHOLD` from `const.py`
- Produces: Test class `TestShouldApply` with 11 test methods

- [ ] **Step 1: Ajouter l'import de DEFAULT_POSITION_THRESHOLD**

In `tests/test_switch.py`, change the import line (near line 138):

```python
from sunny import switch as switch_module
from sunny.const import DEFAULT_POSITION_THRESHOLD
```

- [ ] **Step 2: Ajouter un helper pour mocker `hass.states.get`**

After the `switch_instance` fixture (line 185), add:

```python
def _mock_state(state_value):
    """Crée un mock State avec .state = state_value."""
    state = MagicMock()
    state.state = state_value
    return state
```

- [ ] **Step 3: Ajouter les 11 tests de `_should_apply`**

After line 305, add before the end of file:

```python
class TestShouldApply:
    """Tests unitaires pour la méthode _should_apply."""

    def _make_switch(self, mock_hass):
        coord = MagicMock()
        coord.entry = MagicMock()
        coord.entry.options = {}
        coord.entry.entry_id = "test_entry"
        coord.data = {"Test": {"desired_position": 50, "cover_entity": "cover.test_shutter"}}
        s = switch_module.SunnyAutoControlSwitch(
            coord, "Test", 0, "test_id", "cover.test_shutter", MagicMock(),
        )
        s.hass = mock_hass
        return s

    def test_state_none_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = None
        assert s._should_apply(50, 3, "cover.x") is True

    def test_state_unavailable_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("unavailable")
        assert s._should_apply(50, 3, "cover.x") is True

    def test_state_unknown_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("unknown")
        assert s._should_apply(50, 3, "cover.x") is True

    def test_state_invalid_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("closed")
        assert s._should_apply(50, 3, "cover.x") is True

    def test_same_position_skips(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("50")
        assert s._should_apply(50, 3, "cover.x") is False

    def test_target_zero_always_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("50")
        assert s._should_apply(0, 3, "cover.x") is True

    def test_target_100_always_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("50")
        assert s._should_apply(100, 3, "cover.x") is True

    def test_current_zero_target_zero_skips(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("0")
        assert s._should_apply(0, 3, "cover.x") is False

    def test_change_above_threshold_applies(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("50")
        assert s._should_apply(54, 3, "cover.x") is True

    def test_change_below_threshold_skips(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("50")
        assert s._should_apply(52, 3, "cover.x") is False

    def test_threshold_zero_always_applies_on_change(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.hass.states.get.return_value = _mock_state("50")
        assert s._should_apply(51, 0, "cover.x") is True
```

- [ ] **Step 4: Vérifier que les nouveaux tests échouent**

```bash
python3 -m pytest tests/test_switch.py::TestShouldApply -v
```
Expected: all 11 FAIL with `AttributeError: 'SunnyAutoControlSwitch' object has no attribute '_should_apply'`

- [ ] **Step 5: Commit**

```bash
git add tests/test_switch.py
git commit -m "add failing tests for _should_apply"
```

---

### Task 3: Implémenter `_should_apply` et l'intégrer

**Files:**
- Modify: `custom_components/sunny/switch.py`

**Interfaces:**
- Consumes: `DEFAULT_POSITION_THRESHOLD` from `const.py`
- Produces: `SunnyAutoControlSwitch._should_apply(self, new, threshold, cover_entity) -> bool`
- Modifies: `_handle_coordinator_update()`, `async_turn_on()`

- [ ] **Step 1: Ajouter l'import de DEFAULT_POSITION_THRESHOLD**

In `switch.py`, change:
```python
from .const import DOMAIN
```
To:
```python
from .const import DEFAULT_POSITION_THRESHOLD, DOMAIN
```

- [ ] **Step 2: Ajouter la méthode `_should_apply`**

Dans la classe `SunnyAutoControlSwitch`, avant `async_turn_on` (line 113), ajouter:

```python
    def _should_apply(self, new: int, threshold: int, cover_entity: str) -> bool:
        state = self.hass.states.get(cover_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return True
        try:
            current = int(float(state.state))
        except (ValueError, TypeError):
            return True
        if new == current:
            return False
        if new in (0, 100):
            return True
        return abs(new - current) >= threshold
```

- [ ] **Step 3: Modifier `_handle_coordinator_update`**

Remplacer le bloc `if self._attr_is_on:` (lines 88-94) par:

```python
        if self._attr_is_on:
            desired_position = data.get("desired_position")
            cover_entity = data.get("cover_entity")
            if desired_position is not None and cover_entity:
                threshold = self.coordinator.entry.options.get(
                    "position_threshold", DEFAULT_POSITION_THRESHOLD
                )
                if self._should_apply(desired_position, threshold, cover_entity):
                    self.hass.async_create_task(
                        self._apply_position(cover_entity, desired_position)
                    )
```

- [ ] **Step 4: Modifier `async_turn_on`**

Remplacer le bloc `if data:` dans `async_turn_on` (lines 116-120) par:

```python
        if data:
            desired_position = data.get("desired_position")
            cover_entity = data.get("cover_entity")
            if desired_position is not None and cover_entity:
                threshold = self.coordinator.entry.options.get(
                    "position_threshold", DEFAULT_POSITION_THRESHOLD
                )
                if self._should_apply(desired_position, threshold, cover_entity):
                    await self._apply_position(cover_entity, desired_position)
```

- [ ] **Step 5: Lancer les nouveaux tests**

```bash
python3 -m pytest tests/test_switch.py::TestShouldApply -v
```
Expected: all 11 PASS

- [ ] **Step 6: Lancer tous les tests pour vérifier l'absence de régression**

```bash
python3 -m pytest tests/ -v
```
Expected: all ~99 PASS (88 existing + 11 new)

- [ ] **Step 7: Commit**

```bash
git add custom_components/sunny/switch.py
git commit -m "implement position threshold in switch"
```

---

### Task 4: Ajouter la configuration UI

**Files:**
- Modify: `custom_components/sunny/strings.json`
- Modify: `custom_components/sunny/config_flow.py`

**Interfaces:**
- Consumes: `CONF_POSITION_THRESHOLD`, `DEFAULT_POSITION_THRESHOLD` from `const.py`
- Produces: new action "position_threshold" in options menu, new step `async_step_position_threshold`

- [ ] **Step 1: Ajouter les traductions dans `strings.json`**

Dans le bloc `"options"` > `"step"`, après l'étape `"refresh"` (line 113), ajouter:

```json
      "position_threshold": {
        "title": "Seuil de tolérance de position",
        "data": {
          "position_threshold": "Seuil minimum de changement (%)"
        }
      }
```

Dans `"selector"` > `"action"` > `"options"`, après `"refresh": "Modifier la fréquence de rafraîchissement"`, ajouter:

```json
        "position_threshold": "Changer le seuil de position"
```

- [ ] **Step 2: Ajouter l'import dans `config_flow.py`**

Dans la liste d'imports from `.const`, ajouter `CONF_POSITION_THRESHOLD` et `DEFAULT_POSITION_THRESHOLD`:

```python
from .const import (
    DOMAIN,
    CONF_WEATHER_ENTITY,
    CONF_WINDOWS,
    CONF_WINDOW_NAME,
    CONF_WINDOW_ID,
    CONF_COVER_ENTITY,
    CONF_ORIENTATION,
    CONF_WIDTH,
    CONF_HEIGHT,
    CONF_WALL_THICKNESS,
    CONF_SCREEN_DISTANCE,
    CONF_SCREEN_HEIGHT,
    CONF_TILT_THRESHOLD,
    CONF_SLAT_TRANSMISSION,
    CONF_ALTITUDE,
    CONF_GROUND_ALTITUDE,
    CONF_ZONE_ENTITY,
    CONF_STRATEGY,
    CONF_REFRESH_INTERVAL,
    CONF_POSITION_THRESHOLD,
    CONF_STRATEGY_HIGH,
    CONF_STRATEGY_LOW,
    CONF_TEMP_THRESHOLD,
    CONF_LIT_THRESHOLD,
    CONF_TARGET_ILLUMINATION,
    DEFAULT_NAME,
    DEFAULT_ORIENTATION,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    DEFAULT_WALL_THICKNESS,
    DEFAULT_SCREEN_DISTANCE,
    DEFAULT_SCREEN_HEIGHT,
    DEFAULT_TILT_THRESHOLD,
    DEFAULT_SLAT_TRANSMISSION,
    DEFAULT_ALTITUDE,
    DEFAULT_GROUND_ALTITUDE,
    DEFAULT_STRATEGY,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_POSITION_THRESHOLD,
    DEFAULT_STRATEGY_HIGH,
    DEFAULT_STRATEGY_LOW,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_LIT_THRESHOLD,
    DEFAULT_TARGET_ILLUMINATION,
)
```

- [ ] **Step 3: Ajouter l'import de `NumberSelector` et `NumberSelectorConfig`**

Dans les imports `homeassistant.helpers.selector` (line 12-15), ajouter:

```python
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
```

- [ ] **Step 4: Ajouter l'action dans `async_step_init`**

Dans la chaîne `if/elif` de `async_step_init`, avant `elif action == "done":` (line 284), ajouter:

```python
            elif action == "position_threshold":
                return await self.async_step_position_threshold()
```

- [ ] **Step 5: Ajouter `position_threshold` à la liste des actions du menu**

Dans la ligne `vol.Required("action")` du schema (line 294), ajouter `"position_threshold"`:

```python
            vol.Required("action"): vol.In(["edit", "delete", "add", "weather", "refresh", "position_threshold", "done"]),
```

- [ ] **Step 6: Ajouter la méthode `async_step_position_threshold`**

Après `async_step_refresh` (line 377), ajouter:

```python
    async def async_step_position_threshold(
        self, user_input: dict[str, Any] | None = None
    ):
        if user_input is not None:
            self.data[CONF_POSITION_THRESHOLD] = user_input[CONF_POSITION_THRESHOLD]
            return await self.async_step_init()

        current = self.data.get(CONF_POSITION_THRESHOLD, DEFAULT_POSITION_THRESHOLD)
        return self.async_show_form(
            step_id="position_threshold",
            data_schema=vol.Schema({
                vol.Required(CONF_POSITION_THRESHOLD, default=current):
                    NumberSelector(
                        NumberSelectorConfig(min=0, max=20, step=1, mode=NumberSelectorMode.BOX)
                    ),
            }),
        )
```

- [ ] **Step 7: Lancer tous les tests pour vérifier l'absence de régression**

```bash
python3 -m pytest tests/ -v
```
Expected: all ~99 PASS

- [ ] **Step 8: Commit**

```bash
git add custom_components/sunny/strings.json custom_components/sunny/config_flow.py
git commit -m "add position threshold option in UI"
```

---

### Final verification

```bash
python3 -m pytest tests/ -v
```
Expected: all ~99 PASS, no regressions.