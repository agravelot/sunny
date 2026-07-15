"""Tests unitaires pour le switch de pilotage automatique."""

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


class _MockSwitchEntity:
    _attr_icon = None
    _attr_has_entity_name = False
    _attr_is_on = False
    _attr_unique_id = None
    _attr_device_info = None
    _attr_name = None
    _attr_entity_category = None
    def async_write_ha_state(self):
        pass


class _MockCoordinatorEntity:
    coordinator = None
    def __init__(self, coordinator, *args, context=None, **kwargs):
        self.coordinator = coordinator


class _MockSensorEntity:
    pass


class _MockSelectEntity:
    pass


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


def _setup_ha_mocks():
    ha_switch = MagicMock()
    ha_switch.SwitchEntity = _MockSwitchEntity

    ha_sensor = MagicMock()
    ha_sensor.SensorEntity = _MockSensorEntity
    ha_sensor.SensorStateClass = MagicMock()

    ha_select = MagicMock()
    ha_select.SelectEntity = _MockSelectEntity

    ha_restore = MagicMock()
    ha_restore.RestoreEntity = _MockRestoreEntity

    ha_update = MagicMock()
    ha_update.CoordinatorEntity = _MockCoordinatorEntity
    ha_update.DataUpdateCoordinator = _MockDataUpdateCoordinator

    ha_device_registry = MagicMock()
    ha_device_registry.DeviceInfo = _MockDeviceInfo

    ha_event = MagicMock()
    ha_event.async_track_entity_registry_updated_event = MagicMock()

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

    ha = MagicMock()
    ha.components = MagicMock()
    ha.components.switch = ha_switch
    ha.components.sensor = ha_sensor
    ha.components.select = ha_select
    ha.helpers = ha_helpers
    ha.core = ha_core
    ha.config_entries = ha_config_entries
    ha.const = ha_const

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = ha.components
    sys.modules["homeassistant.components.switch"] = ha_switch
    sys.modules["homeassistant.components.sensor"] = ha_sensor
    sys.modules["homeassistant.components.select"] = ha_select
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

from sunny import switch as switch_module
from sunny.const import DEFAULT_POSITION_THRESHOLD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.fixture
def mock_coordinator(mock_hass):
    coord = MagicMock()
    coord.entry = MagicMock()
    coord.entry.entry_id = "test_entry"
    coord.hass = mock_hass
    coord.data = {
        "Test": {
            "desired_position": 50,
            "cover_entity": "cover.test_shutter",
        },
    }
    return coord


@pytest.fixture
def device_info():
    return MagicMock()


@pytest.fixture
def switch_instance(mock_coordinator, device_info, mock_hass):
    s = switch_module.SunnyAutoControlSwitch(
        mock_coordinator,
        "Test",
        0,
        "test_id",
        "cover.test_shutter",
        device_info,
    )
    s.hass = mock_hass
    s._attr_is_on = False
    return s


def _mock_state(state_value):
    """Crée un mock State avec .state = state_value."""
    state = MagicMock()
    state.state = state_value
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSunnyAutoControlSwitch:
    def test_initial_state_off(self, switch_instance):
        assert switch_instance._attr_is_on is False

    def test_unique_id_format(self, switch_instance):
        assert switch_instance._attr_unique_id == "test_entry_test_id_Test_auto_control"

    def test_entity_name(self, switch_instance):
        assert switch_instance._attr_name == "Test Pilotage auto"
        assert switch_instance._attr_has_entity_name is True

    @pytest.mark.asyncio
    async def test_turn_on_activates(self, switch_instance, mock_hass):
        switch_instance.async_write_ha_state = MagicMock()
        await switch_instance.async_turn_on()
        assert switch_instance._attr_is_on is True
        switch_instance.async_write_ha_state.assert_called()

    @pytest.mark.asyncio
    async def test_turn_on_applies_position(self, switch_instance, mock_coordinator, mock_hass):
        mock_hass.services.async_call.reset_mock()
        await switch_instance.async_turn_on()
        mock_hass.services.async_call.assert_called_once_with(
            "cover", "set_cover_position",
            {"entity_id": "cover.test_shutter", "position": 50},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_turn_on_no_cover_entity(self, switch_instance, mock_coordinator, mock_hass):
        mock_coordinator.data["Test"]["cover_entity"] = None
        mock_hass.services.async_call.reset_mock()
        await switch_instance.async_turn_on()
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_off_deactivates(self, switch_instance):
        switch_instance._attr_is_on = True
        switch_instance.async_write_ha_state = MagicMock()
        await switch_instance.async_turn_off()
        assert switch_instance._attr_is_on is False
        switch_instance.async_write_ha_state.assert_called()

    def test_coord_update_applies_when_on(self, switch_instance, mock_hass):
        switch_instance._attr_is_on = True
        switch_instance.async_write_ha_state = MagicMock()
        switch_instance._handle_coordinator_update()
        mock_hass.async_create_task.assert_called_once()
        switch_instance.async_write_ha_state.assert_called_once()

    def test_coord_update_skips_when_off(self, switch_instance, mock_hass):
        switch_instance._attr_is_on = False
        mock_hass.async_create_task.reset_mock()
        switch_instance._handle_coordinator_update()
        mock_hass.async_create_task.assert_not_called()

    def test_no_data_does_nothing(self, switch_instance, mock_coordinator, mock_hass):
        switch_instance._attr_is_on = True
        mock_hass.async_create_task.reset_mock()
        mock_coordinator.data = {}
        switch_instance._handle_coordinator_update()
        mock_hass.async_create_task.assert_not_called()

    def test_no_desired_position_does_nothing(self, switch_instance, mock_coordinator, mock_hass):
        switch_instance._attr_is_on = True
        mock_hass.async_create_task.reset_mock()
        mock_coordinator.data["Test"]["desired_position"] = None
        switch_instance._handle_coordinator_update()
        mock_hass.async_create_task.assert_not_called()

    def test_no_cover_entity_does_nothing(self, switch_instance, mock_coordinator, mock_hass):
        switch_instance._attr_is_on = True
        mock_hass.async_create_task.reset_mock()
        mock_coordinator.data["Test"]["cover_entity"] = None
        switch_instance._handle_coordinator_update()
        mock_hass.async_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_position_error_is_logged(self, switch_instance, mock_hass):
        mock_hass.services.async_call.side_effect = RuntimeError("cover indisponible")
        switch_instance.async_write_ha_state = MagicMock()

        await switch_instance._apply_position("cover.test_shutter", 50)

        mock_hass.services.async_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_state_on(self, switch_instance):
        switch_instance.async_get_last_state = AsyncMock(return_value=MagicMock(state="on"))
        switch_instance.async_write_ha_state = MagicMock()
        switch_instance._handle_coordinator_update = MagicMock()

        await switch_instance.async_added_to_hass()

        assert switch_instance._attr_is_on is True
        switch_instance._handle_coordinator_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_state_off(self, switch_instance):
        switch_instance.async_get_last_state = AsyncMock(return_value=MagicMock(state="off"))
        switch_instance._handle_coordinator_update = MagicMock()

        await switch_instance.async_added_to_hass()

        assert switch_instance._attr_is_on is False

    @pytest.mark.asyncio
    async def test_restore_no_state_uses_default(self, switch_instance):
        switch_instance.async_get_last_state = AsyncMock(return_value=None)
        switch_instance._handle_coordinator_update = MagicMock()

        await switch_instance.async_added_to_hass()

        assert switch_instance._attr_is_on is False


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