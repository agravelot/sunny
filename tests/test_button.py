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
