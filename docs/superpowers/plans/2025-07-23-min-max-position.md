# Bornes min/max de position par store — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter deux entités number par store (Position min / Position max) et un bouton de réinitialisation, avec clamping de la position désirée dans le coordinator.

**Architecture:** Deux nouvelles plateformes HA natives (`number`, `button`) créent des entités par store. Les valeurs sont persistées dans `entry.options.windows[N]` (même pattern que le `select` stratégie). Le coordinator clamp `desired_position` entre les bornes configurées.

**Tech Stack:** Python 3, Home Assistant (number, button, RestoreEntity, CoordinatorEntity), voluptuous

## Global Constraints

- Code, commentaires, UI en **français**
- Tests sans imports Home Assistant (mock complet comme `test_switch.py`)
- unique_id format : `{entry_id}_{window_id}_{window_name}_{suffix}`
- Persistance via `entry.options` + `async_update_entry` (même pattern que `select.py`)
- Bornes : min=0, max=100, pas=1, mode=BOX

---

### Task 1: Ajouter les constantes (`const.py`)

**Files:**
- Modify: `custom_components/sunny/const.py`

**Interfaces:**
- Produces: `CONF_MIN_POSITION = "min_position"`, `CONF_MAX_POSITION = "max_position"`, `DEFAULT_MIN_POSITION = 0`, `DEFAULT_MAX_POSITION = 100`

- [ ] **Step 1: Ajouter les constantes**

```python
DEFAULT_MIN_POSITION = 0
DEFAULT_MAX_POSITION = 100
```

Ajouter après `DEFAULT_LIT_THRESHOLD` (ligne 66):

```python
CONF_MIN_POSITION = "min_position"
CONF_MAX_POSITION = "max_position"
```

Ajouter après `CONF_TARGET_ILLUMINATION` (ligne 37-38):

```python
DEFAULT_MIN_POSITION = 0
DEFAULT_MAX_POSITION = 100
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/sunny/const.py
git commit -m "add min/max position constants"
```

---

### Task 2: Clamping dans le coordinator (`coordinator.py`)

**Files:**
- Modify: `custom_components/sunny/coordinator.py`

**Interfaces:**
- Consumes: `CONF_MIN_POSITION`, `CONF_MAX_POSITION` from const.py
- Produces: `desired_position` dans `data` est maintenant clampé entre min/max

- [ ] **Step 1: Ajouter l'import des constantes**

Dans le bloc d'imports existant (ligne 11-28), ajouter:

```python
    CONF_MIN_POSITION,
    CONF_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DEFAULT_MAX_POSITION,
```

- [ ] **Step 2: Ajouter le clamping**

Après la ligne `data["desired_position"] = strategy.compute_position(data)` (ligne 233), ajouter :

```python
            data["desired_position"] = strategy.compute_position(data)
            min_pos = int(win.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION))
            max_pos = int(win.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION))
            data["desired_position"] = max(min_pos, min(max_pos, data["desired_position"]))
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/sunny/coordinator.py
git commit -m "clamp desired_position between min/max bounds"
```

---

### Task 3: Créer la plateforme `number` (`number.py`)

**Files:**
- Create: `custom_components/sunny/number.py`

**Interfaces:**
- Consumes: `CONF_MIN_POSITION`, `CONF_MAX_POSITION`, `DEFAULT_MIN_POSITION`, `DEFAULT_MAX_POSITION`, `DOMAIN` from const.py; `SunnyCoordinator` from coordinator.py; `fallback_device_info`, `resolve_cover_device` from sensor.py
- Produces: `async_setup_entry` pour le platform setup; classes `SunnyMinPositionNumber`, `SunnyMaxPositionNumber`

- [ ] **Step 1: Créer le fichier complet**

```python
"""Plateforme number pour les bornes min/max de position."""

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MAX_POSITION,
    CONF_MIN_POSITION,
    DEFAULT_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DOMAIN,
)
from .coordinator import SunnyCoordinator
from .sensor import fallback_device_info, resolve_cover_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SunnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    windows = entry.options.get("windows", [])

    entities = []
    pending_covers: set[str] = set()

    for idx, win in enumerate(windows):
        name = win["name"]
        cover_entity_id = win.get("cover_entity", "")
        window_id = win.get("id", win.get("cover_entity", str(idx)))

        if cover_entity_id:
            device_info = await resolve_cover_device(
                hass, entry, cover_entity_id, name
            )
            if device_info is None:
                pending_covers.add(cover_entity_id)
                continue
        else:
            device_info = fallback_device_info(entry, name)

        entities.append(
            SunnyMinPositionNumber(coordinator, name, idx, window_id, device_info)
        )
        entities.append(
            SunnyMaxPositionNumber(coordinator, name, idx, window_id, device_info)
        )

    if pending_covers:
        @callback
        def _on_cover_registered(event):
            entity_id = event.data.get("entity_id")
            if entity_id in pending_covers:
                pending_covers.discard(entity_id)
                hass.async_create_task(
                    hass.config_entries.async_reload(entry.entry_id)
                )

        entry.async_on_unload(
            async_track_entity_registry_updated_event(
                hass, set(pending_covers), _on_cover_registered
            )
        )

    async_add_entities(entities)


class SunnyBasePositionNumber(CoordinatorEntity, NumberEntity, RestoreEntity):
    """Classe de base pour les entités number de bornes."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_idx: int,
        window_id: str,
        device_info,
        number_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._window_idx = window_idx
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{window_id}_{window_name}_{number_type}"
        )
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        windows = self.coordinator.entry.options.get("windows", [])
        if self._window_idx < len(windows):
            win = windows[self._window_idx]
            key = self._get_config_key()
            return float(win.get(key, self._get_default()))
        return float(self._get_default())

    def _get_config_key(self) -> str:
        raise NotImplementedError

    def _get_default(self) -> int:
        raise NotImplementedError

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(value)
        new_options = dict(self.coordinator.entry.options)
        windows = list(new_options.get("windows", []))
        if self._window_idx < len(windows):
            windows[self._window_idx] = dict(windows[self._window_idx])
            windows[self._window_idx][self._get_config_key()] = int_value
        new_options["windows"] = windows
        self.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        self.coordinator.entry = self.hass.config_entries.async_get_entry(
            self.coordinator.entry.entry_id
        )
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unavailable", "unknown"):
            try:
                await self.async_set_native_value(float(last_state.state))
            except (ValueError, TypeError):
                pass


class SunnyMinPositionNumber(SunnyBasePositionNumber):
    """Entité number pour la position minimale désirée."""

    _attr_icon = "mdi:arrow-collapse-down"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_idx: int,
        window_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator, window_name, window_idx, window_id, device_info, "min_position")
        self._attr_name = f"{window_name} Position min"

    def _get_config_key(self) -> str:
        return CONF_MIN_POSITION

    def _get_default(self) -> int:
        return DEFAULT_MIN_POSITION


class SunnyMaxPositionNumber(SunnyBasePositionNumber):
    """Entité number pour la position maximale désirée."""

    _attr_icon = "mdi:arrow-collapse-up"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_idx: int,
        window_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator, window_name, window_idx, window_id, device_info, "max_position")
        self._attr_name = f"{window_name} Position max"

    def _get_config_key(self) -> str:
        return CONF_MAX_POSITION

    def _get_default(self) -> int:
        return DEFAULT_MAX_POSITION
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/sunny/number.py
git commit -m "add number platform for min/max position bounds"
```

---

### Task 4: Créer la plateforme `button` (`button.py`)

**Files:**
- Create: `custom_components/sunny/button.py`

**Interfaces:**
- Consumes: `DOMAIN` from const.py; `SunnyCoordinator` from coordinator.py; `fallback_device_info`, `resolve_cover_device` from sensor.py
- Produces: `async_setup_entry`; class `SunnyResetBoundsButton`

- [ ] **Step 1: Créer le fichier complet**

```python
"""Plateforme button pour réinitialiser les bornes de position."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DOMAIN,
)
from .coordinator import SunnyCoordinator
from .sensor import fallback_device_info, resolve_cover_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SunnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    windows = entry.options.get("windows", [])

    entities = []
    pending_covers: set[str] = set()

    for idx, win in enumerate(windows):
        name = win["name"]
        cover_entity_id = win.get("cover_entity", "")
        window_id = win.get("id", win.get("cover_entity", str(idx)))

        if cover_entity_id:
            device_info = await resolve_cover_device(
                hass, entry, cover_entity_id, name
            )
            if device_info is None:
                pending_covers.add(cover_entity_id)
                continue
        else:
            device_info = fallback_device_info(entry, name)

        entities.append(
            SunnyResetBoundsButton(coordinator, name, idx, window_id, device_info)
        )

    if pending_covers:
        @callback
        def _on_cover_registered(event):
            entity_id = event.data.get("entity_id")
            if entity_id in pending_covers:
                pending_covers.discard(entity_id)
                hass.async_create_task(
                    hass.config_entries.async_reload(entry.entry_id)
                )

        entry.async_on_unload(
            async_track_entity_registry_updated_event(
                hass, set(pending_covers), _on_cover_registered
            )
        )

    async_add_entities(entities)


class SunnyResetBoundsButton(CoordinatorEntity, ButtonEntity):
    """Bouton pour réinitialiser les bornes min/max à 0/100."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:restore"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_idx: int,
        window_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._window_idx = window_idx
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{window_id}_{window_name}_reset_bounds"
        )
        self._attr_device_info = device_info
        self._attr_name = f"{window_name} Réinitialiser bornes"

    async def async_press(self) -> None:
        new_options = dict(self.coordinator.entry.options)
        windows = list(new_options.get("windows", []))
        if self._window_idx < len(windows):
            windows[self._window_idx] = dict(windows[self._window_idx])
            windows[self._window_idx]["min_position"] = DEFAULT_MIN_POSITION
            windows[self._window_idx]["max_position"] = DEFAULT_MAX_POSITION
        new_options["windows"] = windows
        self.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        self.coordinator.entry = self.hass.config_entries.async_get_entry(
            self.coordinator.entry.entry_id
        )
        await self.coordinator.async_request_refresh()
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/sunny/button.py
git commit -m "add button platform for resetting position bounds"
```

---

### Task 5: Mettre à jour les plateformes et le cleanup

**Files:**
- Modify: `custom_components/sunny/__init__.py`
- Modify: `custom_components/sunny/config_flow.py`

**Interfaces:**
- Consumes: plateformes `number`, `button` existent désormais
- Produces: `PLATFORMS` inclut `number` et `button` ; `_cleanup_window_entities` nettoie les entités number/button

- [ ] **Step 1: Ajouter les plateformes dans `__init__.py`**

Remplacer la ligne 12:

```python
PLATFORMS = ["sensor", "select", "switch", "number", "button"]
```

- [ ] **Step 2: Ajouter les domaines dans `_cleanup_window_entities` (`config_flow.py`)**

Dans la boucle `for domain, suffix in [...]` (lignes 207-213), ajouter:

```python
        ("number", "min_position"),
        ("number", "max_position"),
        ("button", "reset_bounds"),
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/sunny/__init__.py custom_components/sunny/config_flow.py
git commit -m "register number and button platforms, add cleanup"
```

---

### Task 6: Tests pour la plateforme `number` (`tests/test_number.py`)

**Files:**
- Create: `tests/test_number.py`

**Interfaces:**
- Consumes: `sunny.number` module (SunnyMinPositionNumber, SunnyMaxPositionNumber)
- Produces: Tests unitaires pour les entités number

- [ ] **Step 1: Créer le fichier de test**

```python
"""Tests unitaires pour les entités number de bornes min/max."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Mocks des modules Home Assistant
# ---------------------------------------------------------------------------

class _MockRestoreEntity:
    async def async_added_to_hass(self) -> None:
        pass
    async def async_get_last_state(self):
        return None


class _MockNumberEntity:
    _attr_icon = None
    _attr_has_entity_name = False
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = "box"
    _attr_unique_id = None
    _attr_device_info = None
    _attr_name = None
    _attr_entity_category = None
    def async_write_ha_state(self):
        pass
    def async_on_remove(self, callback):
        pass


class _MockCoordinatorEntity:
    coordinator = None
    def __init__(self, coordinator, *args, context=None, **kwargs):
        self.coordinator = coordinator


class _MockDataUpdateCoordinator:
    def __init__(self, *args, **kwargs):
        pass
    async def async_config_entry_first_refresh(self):
        pass
    async def async_request_refresh(self):
        pass


class _MockDeviceInfo:
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockButtonEntity:
    pass


def _setup_ha_mocks():
    ha_number = MagicMock()
    ha_number.NumberEntity = _MockNumberEntity
    ha_number.NumberMode = MagicMock()
    ha_number.NumberMode.BOX = "box"

    ha_restore = MagicMock()
    ha_restore.RestoreEntity = _MockRestoreEntity

    ha_update = MagicMock()
    ha_update.CoordinatorEntity = _MockCoordinatorEntity
    ha_update.DataUpdateCoordinator = _MockDataUpdateCoordinator

    ha_device_registry = MagicMock()
    ha_device_registry.DeviceInfo = _MockDeviceInfo

    ha_event = MagicMock()
    ha_event.async_track_entity_registry_updated_event = MagicMock()
    ha_event.async_track_state_change_event = MagicMock(return_value=MagicMock())

    ha_helpers = MagicMock()
    ha_helpers.device_registry = ha_device_registry
    ha_helpers.entity_registry = MagicMock()
    ha_helpers.event = ha_event

    ha_core = MagicMock()
    ha_core.HomeAssistant = MagicMock
    ha_core.callback = lambda f: f

    ha_config_entries = MagicMock()
    ha_config_entries.ConfigEntry = MagicMock

    ha_entity_platform = MagicMock()
    ha_entity_platform.AddEntitiesCallback = MagicMock

    ha_const = MagicMock()
    ha_const.PERCENTAGE = "%"

    ha_button = MagicMock()
    ha_button.ButtonEntity = _MockButtonEntity

    ha = MagicMock()
    ha.components = MagicMock()
    ha.components.number = ha_number
    ha.components.button = ha_button
    ha.helpers = ha_helpers
    ha.core = ha_core
    ha.config_entries = ha_config_entries
    ha.const = ha_const

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = ha.components
    sys.modules["homeassistant.components.number"] = ha_number
    sys.modules["homeassistant.components.button"] = ha_button
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.restore_state"] = ha_restore
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_update
    sys.modules["homeassistant.helpers.device_registry"] = ha_device_registry
    sys.modules["homeassistant.helpers.event"] = ha_event
    sys.modules["homeassistant.helpers.entity_platform"] = ha_entity_platform
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.const"] = ha_const

    # Also mock sensor module for fallback_device_info import
    class _MockSensorEntity:
        pass
    ha_sensor = MagicMock()
    ha_sensor.SensorEntity = _MockSensorEntity
    ha_sensor.SensorStateClass = MagicMock()
    sys.modules["homeassistant.components.sensor"] = ha_sensor


_setup_ha_mocks()

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC.parent))

from sunny import number as number_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=MagicMock(
        options={"windows": []}
    ))
    return hass


@pytest.fixture
def mock_coordinator(mock_hass):
    coord = MagicMock()
    coord.entry = MagicMock()
    coord.entry.entry_id = "test_entry"
    coord.entry.options = {
        "windows": [
            {"name": "Test", "cover_entity": "cover.test_shutter"},
        ]
    }
    coord.hass = mock_hass
    coord.async_request_refresh = AsyncMock()
    return coord


@pytest.fixture
def device_info():
    return MagicMock()


@pytest.fixture
def min_number(mock_coordinator, device_info, mock_hass):
    n = number_module.SunnyMinPositionNumber(
        mock_coordinator, "Test", 0, "test_id", device_info,
    )
    n.hass = mock_hass
    return n


@pytest.fixture
def max_number(mock_coordinator, device_info, mock_hass):
    n = number_module.SunnyMaxPositionNumber(
        mock_coordinator, "Test", 0, "test_id", device_info,
    )
    n.hass = mock_hass
    return n


# ---------------------------------------------------------------------------
# Tests SunnyMinPositionNumber
# ---------------------------------------------------------------------------

class TestSunnyMinPositionNumber:
    def test_creation(self, min_number):
        assert min_number._attr_name == "Test Position min"
        assert min_number._attr_has_entity_name is True

    def test_unique_id(self, min_number):
        assert min_number._attr_unique_id == "test_entry_test_id_Test_min_position"

    def test_native_min_max_step(self, min_number):
        assert min_number._attr_native_min_value == 0
        assert min_number._attr_native_max_value == 100
        assert min_number._attr_native_step == 1

    def test_native_value_default(self, min_number, mock_coordinator):
        mock_coordinator.entry.options = {"windows": [{"name": "Test"}]}
        assert min_number.native_value == 0.0

    def test_native_value_from_options(self, min_number, mock_coordinator):
        mock_coordinator.entry.options = {
            "windows": [{"name": "Test", "min_position": 30}]
        }
        assert min_number.native_value == 30.0

    def test_native_value_out_of_range(self, min_number, mock_coordinator):
        mock_coordinator.entry.options = {
            "windows": []
        }
        assert min_number.native_value == 0.0

    @pytest.mark.asyncio
    async def test_set_value(self, min_number, mock_coordinator, mock_hass):
        mock_hass.config_entries.async_update_entry.reset_mock()
        await min_number.async_set_native_value(25.0)
        mock_hass.config_entries.async_update_entry.assert_called_once()
        args = mock_hass.config_entries.async_update_entry.call_args
        assert args[1]["options"]["windows"][0]["min_position"] == 25
        mock_coordinator.async_request_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# Tests SunnyMaxPositionNumber
# ---------------------------------------------------------------------------

class TestSunnyMaxPositionNumber:
    def test_creation(self, max_number):
        assert max_number._attr_name == "Test Position max"

    def test_unique_id(self, max_number):
        assert max_number._attr_unique_id == "test_entry_test_id_Test_max_position"

    def test_native_value_default(self, max_number, mock_coordinator):
        mock_coordinator.entry.options = {"windows": [{"name": "Test"}]}
        assert max_number.native_value == 100.0

    def test_native_value_from_options(self, max_number, mock_coordinator):
        mock_coordinator.entry.options = {
            "windows": [{"name": "Test", "max_position": 80}]
        }
        assert max_number.native_value == 80.0

    @pytest.mark.asyncio
    async def test_set_value(self, max_number, mock_coordinator, mock_hass):
        mock_hass.config_entries.async_update_entry.reset_mock()
        await max_number.async_set_native_value(75.0)
        mock_hass.config_entries.async_update_entry.assert_called_once()
        args = mock_hass.config_entries.async_update_entry.call_args
        assert args[1]["options"]["windows"][0]["max_position"] == 75
        mock_coordinator.async_request_refresh.assert_called_once()
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils passent**

```bash
python3 -m pytest tests/test_number.py -v
```

Expected: 9 tests passent

- [ ] **Step 3: Commit**

```bash
git add tests/test_number.py
git commit -m "add number platform tests"
```

---

### Task 7: Tests pour la plateforme `button` (`tests/test_button.py`)

**Files:**
- Create: `tests/test_button.py`

**Interfaces:**
- Consumes: `sunny.button` module (SunnyResetBoundsButton)
- Produces: Tests unitaires pour l'entité button

- [ ] **Step 1: Créer le fichier de test**

```python
"""Tests unitaires pour le bouton de réinitialisation des bornes."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

class _MockButtonEntity:
    _attr_icon = None
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_device_info = None
    _attr_name = None
    _attr_entity_category = None
    def async_write_ha_state(self):
        pass
    def async_on_remove(self, callback):
        pass


class _MockCoordinatorEntity:
    coordinator = None
    def __init__(self, coordinator, *args, context=None, **kwargs):
        self.coordinator = coordinator


class _MockDataUpdateCoordinator:
    def __init__(self, *args, **kwargs):
        pass
    async def async_config_entry_first_refresh(self):
        pass
    async def async_request_refresh(self):
        pass


class _MockDeviceInfo:
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockNumberEntity:
    pass


class _MockSensorEntity:
    pass


def _setup_ha_mocks():
    ha_button = MagicMock()
    ha_button.ButtonEntity = _MockButtonEntity

    ha_number = MagicMock()
    ha_number.NumberEntity = _MockNumberEntity

    ha_restore = MagicMock()
    ha_restore.RestoreEntity = MagicMock()

    ha_update = MagicMock()
    ha_update.CoordinatorEntity = _MockCoordinatorEntity
    ha_update.DataUpdateCoordinator = _MockDataUpdateCoordinator

    ha_device_registry = MagicMock()
    ha_device_registry.DeviceInfo = _MockDeviceInfo

    ha_event = MagicMock()
    ha_event.async_track_entity_registry_updated_event = MagicMock()
    ha_event.async_track_state_change_event = MagicMock(return_value=MagicMock())

    ha_helpers = MagicMock()
    ha_helpers.device_registry = ha_device_registry
    ha_helpers.entity_registry = MagicMock()
    ha_helpers.event = ha_event

    ha_core = MagicMock()
    ha_core.HomeAssistant = MagicMock
    ha_core.callback = lambda f: f

    ha_config_entries = MagicMock()
    ha_config_entries.ConfigEntry = MagicMock

    ha_entity_platform = MagicMock()
    ha_entity_platform.AddEntitiesCallback = MagicMock

    ha_const = MagicMock()
    ha_const.PERCENTAGE = "%"

    ha_sensor = MagicMock()
    ha_sensor.SensorEntity = _MockSensorEntity
    ha_sensor.SensorStateClass = MagicMock()

    ha = MagicMock()
    ha.components = MagicMock()
    ha.components.button = ha_button
    ha.components.number = ha_number
    ha.components.sensor = ha_sensor
    ha.helpers = ha_helpers
    ha.core = ha_core
    ha.config_entries = ha_config_entries
    ha.const = ha_const

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = ha.components
    sys.modules["homeassistant.components.button"] = ha_button
    sys.modules["homeassistant.components.number"] = ha_number
    sys.modules["homeassistant.components.sensor"] = ha_sensor
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.restore_state"] = ha_restore
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_update
    sys.modules["homeassistant.helpers.device_registry"] = ha_device_registry
    sys.modules["homeassistant.helpers.event"] = ha_event
    sys.modules["homeassistant.helpers.entity_platform"] = ha_entity_platform
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.const"] = ha_const


_setup_ha_mocks()

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC.parent))

from sunny import button as button_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=MagicMock(
        options={"windows": []}
    ))
    return hass


@pytest.fixture
def mock_coordinator(mock_hass):
    coord = MagicMock()
    coord.entry = MagicMock()
    coord.entry.entry_id = "test_entry"
    coord.entry.options = {
        "windows": [
            {"name": "Test", "cover_entity": "cover.test_shutter"},
        ]
    }
    coord.hass = mock_hass
    coord.async_request_refresh = AsyncMock()
    return coord


@pytest.fixture
def device_info():
    return MagicMock()


@pytest.fixture
def reset_button(mock_coordinator, device_info, mock_hass):
    b = button_module.SunnyResetBoundsButton(
        mock_coordinator, "Test", 0, "test_id", device_info,
    )
    b.hass = mock_hass
    return b


# ---------------------------------------------------------------------------
# Tests SunnyResetBoundsButton
# ---------------------------------------------------------------------------

class TestSunnyResetBoundsButton:
    def test_creation(self, reset_button):
        assert reset_button._attr_name == "Test Réinitialiser bornes"
        assert reset_button._attr_has_entity_name is True

    def test_unique_id(self, reset_button):
        assert reset_button._attr_unique_id == "test_entry_test_id_Test_reset_bounds"

    @pytest.mark.asyncio
    async def test_press_resets(self, reset_button, mock_coordinator, mock_hass):
        mock_hass.config_entries.async_update_entry.reset_mock()
        await reset_button.async_press()
        mock_hass.config_entries.async_update_entry.assert_called_once()
        args = mock_hass.config_entries.async_update_entry.call_args
        assert args[1]["options"]["windows"][0]["min_position"] == 0
        assert args[1]["options"]["windows"][0]["max_position"] == 100
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_press_empty_windows(self, reset_button, mock_coordinator, mock_hass):
        mock_coordinator.entry.options = {"windows": []}
        mock_hass.config_entries.async_update_entry.reset_mock()
        await reset_button.async_press()
        mock_hass.config_entries.async_update_entry.assert_called_once()
        args = mock_hass.config_entries.async_update_entry.call_args
        assert args[1]["options"]["windows"] == []
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils passent**

```bash
python3 -m pytest tests/test_button.py -v
```

Expected: 4 tests passent

- [ ] **Step 3: Commit**

```bash
git add tests/test_button.py
git commit -m "add button platform tests"
```

---

### Task 8: Vérification finale — tous les tests

**Files:** (aucun)

- [ ] **Step 1: Lancer tous les tests**

```bash
python3 -m pytest tests/ -v
```

Expected: 88 + 9 + 4 = 101 tests passent

- [ ] **Step 2: Vérifier qu'aucun fichier importé ne manque**

```bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, 'custom_components')
from sunny import number, button, const, coordinator
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Commit final (si nécessaire)**

Si tout est OK, aucun commit supplémentaire nécessaire.