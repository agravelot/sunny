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