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
    def async_on_remove(self, callback):
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


def _mock_state(state_value, current_position=None):
    """Crée un mock State avec .state = state_value et attributes."""
    state = MagicMock()
    state.state = state_value
    attrs = {}
    if current_position is not None:
        attrs["current_position"] = current_position
    state.attributes = attrs
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
    async def test_turn_on_sets_last_sent_position(self, switch_instance, mock_coordinator, mock_hass):
        switch_instance._last_sent_position = None
        mock_hass.services.async_call.reset_mock()
        await switch_instance.async_turn_on()
        assert switch_instance._last_sent_position == 50
        mock_hass.services.async_call.assert_called_once()

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

    def test_coord_update_sets_last_sent_position(self, switch_instance, mock_hass):
        switch_instance._attr_is_on = True
        switch_instance._last_sent_position = None
        switch_instance.async_write_ha_state = MagicMock()
        switch_instance._handle_coordinator_update()
        assert switch_instance._last_sent_position == 50
        mock_hass.async_create_task.assert_called_once()

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


class TestOnCoverStateChange:
    """Tests unitaires pour la détection d'intervention manuelle."""

    def _make_switch(self, mock_hass, desired_position=50):
        coord = MagicMock()
        coord.entry = MagicMock()
        coord.entry.options = {}
        coord.entry.entry_id = "test_entry"
        coord.data = {
            "Test": {
                "desired_position": desired_position,
                "cover_entity": "cover.test_shutter",
            },
        }
        s = switch_module.SunnyAutoControlSwitch(
            coord, "Test", 0, "test_id", "cover.test_shutter", MagicMock(),
        )
        s.hass = mock_hass
        s.async_write_ha_state = MagicMock()
        return s

    def _event(self, state_value, current_position=None):
        new_state = _mock_state(state_value, current_position)
        event = MagicMock()
        event.data = {"new_state": new_state}
        return event

    def test_manual_change_disables_auto_control(self, mock_hass):
        s = self._make_switch(mock_hass)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("30"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()

    def test_position_matches_desired_is_ignored(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=50)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("50"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_position_within_threshold_is_ignored(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=50)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("52"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_self_applying_blocks_detection(self, mock_hass):
        s = self._make_switch(mock_hass)
        s._attr_is_on = True
        s._self_applying = True

        s._on_cover_state_change(self._event("30"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_already_off_does_nothing(self, mock_hass):
        s = self._make_switch(mock_hass)
        s._attr_is_on = False
        s._self_applying = False

        s._on_cover_state_change(self._event("30"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_not_called()

    def test_no_new_state_does_nothing(self, mock_hass):
        s = self._make_switch(mock_hass)
        s._attr_is_on = True
        s._self_applying = False

        event = MagicMock()
        event.data = {}
        s._on_cover_state_change(event)

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_invalid_state_value_does_nothing(self, mock_hass):
        s = self._make_switch(mock_hass)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("unavailable"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_no_coordinator_data_does_nothing(self, mock_hass):
        s = self._make_switch(mock_hass)
        s.coordinator.data = {}
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("30"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_desired_zero_position_change_disables(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=0)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("50"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()

    def test_desired_100_position_change_disables(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=100)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("70"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()

    def test_desired_zero_cover_at_zero_ignored(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=0)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("0"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_desired_100_cover_at_100_ignored(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=100)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("100"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_cover_with_position_in_attributes_disables(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=70)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("open", current_position=30))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()

    def test_cover_with_position_in_attributes_matches_desired(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=70)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("open", current_position=70))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_cover_with_closed_state_and_position_in_attributes(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=0)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("closed", current_position=0))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_last_sent_position_match_ignored_even_if_desired_changed(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=30)
        s._attr_is_on = True
        s._self_applying = False
        s._last_sent_position = 50

        s._on_cover_state_change(self._event("50"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_last_sent_position_within_threshold_ignored(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=30)
        s._attr_is_on = True
        s._self_applying = False
        s._last_sent_position = 50

        s._on_cover_state_change(self._event("52"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_last_sent_position_mismatch_disables(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=50)
        s._attr_is_on = True
        s._self_applying = False
        s._last_sent_position = 50

        s._on_cover_state_change(self._event("20"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()

    def test_last_sent_position_none_does_not_block(self, mock_hass):
        s = self._make_switch(mock_hass, desired_position=50)
        s._attr_is_on = True
        s._self_applying = False
        s._last_sent_position = None

        s._on_cover_state_change(self._event("30"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()


class TestResolvePosition:
    """Tests unitaires pour _resolve_position."""

    def test_from_state_value(self):
        state = _mock_state("50")
        result = switch_module.SunnyAutoControlSwitch._resolve_position(state)
        assert result == 50

    def test_from_attribute(self):
        state = _mock_state("open", current_position=75)
        result = switch_module.SunnyAutoControlSwitch._resolve_position(state)
        assert result == 75

    def test_attribute_takes_priority(self):
        state = _mock_state("100", current_position=30)
        result = switch_module.SunnyAutoControlSwitch._resolve_position(state)
        assert result == 30

    def test_closed_state(self):
        state = _mock_state("closed", current_position=0)
        result = switch_module.SunnyAutoControlSwitch._resolve_position(state)
        assert result == 0

    def test_unavailable_returns_none(self):
        state = _mock_state("unavailable")
        result = switch_module.SunnyAutoControlSwitch._resolve_position(state)
        assert result is None

    def test_no_position_anywhere_returns_none(self):
        state = _mock_state("open")
        result = switch_module.SunnyAutoControlSwitch._resolve_position(state)
        assert result is None


class TestLastSentPositionConcurrency:
    """Tests de concurrence entre ticks du coordinator."""

    def _make(self, mock_hass, desired_position=50, last_sent=50):
        coord = MagicMock()
        coord.entry = MagicMock()
        coord.entry.options = {}
        coord.entry.entry_id = "test_entry"
        coord.data = {
            "Test": {
                "desired_position": desired_position,
                "cover_entity": "cover.test_shutter",
            },
        }
        s = switch_module.SunnyAutoControlSwitch(
            coord, "Test", 0, "test_id", "cover.test_shutter", MagicMock(),
        )
        s.hass = mock_hass
        s.async_write_ha_state = MagicMock()
        s._last_sent_position = last_sent
        return s

    def _event(self, state_value):
        new_state = _mock_state(state_value)
        event = MagicMock()
        event.data = {"new_state": new_state}
        return event

    def test_tick2_overwrites_last_sent_close_values_still_ignored(self, mock_hass):
        """Tick1: last_sent=50, cover va à 50.
        Tick2: last_sent=53, recalcule desired=53.
        Event arrive avec position=50 (de tick1).
        abs(50-53)=3 ≤ threshold(3) → ignoré par seuil."""
        s = self._make(mock_hass, desired_position=53, last_sent=53)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("50"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()

    def test_tick2_overwrites_last_sent_far_apart_disables(self, mock_hass):
        """Tick1: last_sent=50, cover va à 50.
        Tick2: last_sent=80, recalcule desired=80.
        Event arrive avec position=50 (de tick1).
        abs(50-80)=30 > threshold(3) → désactive.
        Ce cas est très improbable en pratique (ticks espacés de 5 min)."""
        s = self._make(mock_hass, desired_position=80, last_sent=80)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("50"))

        assert s._attr_is_on is False
        s.async_write_ha_state.assert_called_once()

    def test_tick2_same_last_sent_no_conflict(self, mock_hass):
        """Tick1 et tick2 calculent la même position, pas de conflit."""
        s = self._make(mock_hass, desired_position=50, last_sent=50)
        s._attr_is_on = True
        s._self_applying = False

        s._on_cover_state_change(self._event("50"))

        assert s._attr_is_on is True
        s.async_write_ha_state.assert_not_called()