"""Tests unitaires pour _resolve_lux_sensors du coordinateur."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC.parent))


# ---------------------------------------------------------------------------
# Mocks des modules Home Assistant
# ---------------------------------------------------------------------------

class _MockDataUpdateCoordinator:
    def __init__(self, *args, **kwargs):
        pass
    async def async_config_entry_first_refresh(self):
        pass
    async def async_request_refresh(self):
        pass


class _MockCoordinatorEntity:
    coordinator = None
    def __init__(self, coordinator, *args, context=None, **kwargs):
        self.coordinator = coordinator


def _setup_ha_mocks():
    ha_update = MagicMock()
    ha_update.CoordinatorEntity = _MockCoordinatorEntity
    ha_update.DataUpdateCoordinator = _MockDataUpdateCoordinator

    ha_entity_registry = MagicMock()

    ha_core = MagicMock()
    ha_core.HomeAssistant = MagicMock
    ha_core.callback = lambda f: f

    ha_config_entries = MagicMock()
    ha_config_entries.ConfigEntry = MagicMock

    ha_helpers = MagicMock()
    ha_helpers.entity_registry = ha_entity_registry

    ha = MagicMock()
    ha.components = MagicMock()
    ha.helpers = ha_helpers
    ha.core = ha_core
    ha.config_entries = ha_config_entries

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = ha.components
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.entity_registry"] = ha_entity_registry
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_update
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries


_setup_ha_mocks()

import sunny.coordinator as coordinator_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_entity(entity_id, domain, area_id, device_class, original_device_class, disabled):
    """Crée un mock EntityEntry."""
    entity = MagicMock()
    entity.entity_id = entity_id
    entity.domain = domain
    entity.area_id = area_id
    entity.device_class = device_class
    entity.original_device_class = original_device_class
    entity.disabled = disabled
    return entity


def _mock_entity_registry(entities):
    """Crée un mock d'entity_registry avec une liste d'entités."""
    ent_reg = MagicMock()
    ent_reg.entities = {e.entity_id: e for e in entities}
    return ent_reg


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    return hass


@pytest.fixture
def coordinator_instance(mock_hass):
    """Crée une instance de SunnyCoordinator avec un mock hass."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.options = {}

    coord = coordinator_module.SunnyCoordinator(mock_hass, entry)
    coord.hass = mock_hass
    return coord


# ---------------------------------------------------------------------------
# Tests _resolve_lux_sensors
# ---------------------------------------------------------------------------

class TestResolveLuxSensors:
    """Tests pour _resolve_lux_sensors."""

    def test_explicit_lux_sensors_returns_them(self, coordinator_instance, mock_hass):
        win = {"lux_sensors": ["sensor.lux_a", "sensor.lux_b"]}
        result = coordinator_instance._resolve_lux_sensors(win)
        assert result == ["sensor.lux_a", "sensor.lux_b"]

    def test_explicit_lux_sensors_string_converted_to_list(self, coordinator_instance, mock_hass):
        win = {"lux_sensors": "sensor.lux_solo"}
        result = coordinator_instance._resolve_lux_sensors(win)
        assert result == ["sensor.lux_solo"]

    def test_explicit_lux_sensors_filters_empty_strings(self, coordinator_instance, mock_hass):
        win = {"lux_sensors": ["sensor.lux_a", "", "sensor.lux_c"]}
        result = coordinator_instance._resolve_lux_sensors(win)
        assert result == ["sensor.lux_a", "sensor.lux_c"]

    def test_explicit_lux_sensors_filters_non_string(self, coordinator_instance, mock_hass):
        win = {"lux_sensors": ["sensor.lux_a", None, 42]}
        result = coordinator_instance._resolve_lux_sensors(win)
        assert result == ["sensor.lux_a"]

    def test_no_lux_area_and_no_sensors_returns_empty(self, coordinator_instance, mock_hass):
        win = {}
        result = coordinator_instance._resolve_lux_sensors(win)
        assert result == []

    def test_finds_sensor_by_area_and_original_device_class(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.salon_lux", "sensor", "salon",
            device_class=None, original_device_class="illuminance", disabled=False,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == ["sensor.salon_lux"]

    def test_finds_sensor_by_area_and_user_device_class(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.salon_lux", "sensor", "salon",
            device_class="illuminance", original_device_class="illuminance", disabled=False,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == ["sensor.salon_lux"]

    def test_ignores_sensor_with_wrong_area(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.bureau_lux", "sensor", "bureau",
            device_class=None, original_device_class="illuminance", disabled=False,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == []

    def test_ignores_sensor_with_wrong_device_class(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.salon_temp", "sensor", "salon",
            device_class="temperature", original_device_class="temperature", disabled=False,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == []

    def test_ignores_user_overridden_device_class(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.salon_lux", "sensor", "salon",
            device_class="temperature", original_device_class="illuminance", disabled=False,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == []

    def test_ignores_disabled_sensor(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.salon_lux", "sensor", "salon",
            device_class=None, original_device_class="illuminance", disabled=True,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == []

    def test_ignores_non_sensor_entity(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "binary_sensor.salon_lux", "binary_sensor", "salon",
            device_class=None, original_device_class="illuminance", disabled=False,
        )
        ent_reg = _mock_entity_registry([entity])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == []

    def test_multiple_sensors_in_same_area(self, coordinator_instance, mock_hass):
        e1 = _make_mock_entity(
            "sensor.salon_lux_1", "sensor", "salon",
            device_class=None, original_device_class="illuminance", disabled=False,
        )
        e2 = _make_mock_entity(
            "sensor.salon_lux_2", "sensor", "salon",
            device_class="illuminance", original_device_class="illuminance", disabled=False,
        )
        ent_reg = _mock_entity_registry([e1, e2])

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert sorted(result) == sorted(["sensor.salon_lux_1", "sensor.salon_lux_2"])