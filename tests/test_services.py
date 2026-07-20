"""Tests unitaires pour les services Sunny."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC.parent))

# ---------------------------------------------------------------------------
# Mocks des modules Home Assistant
# ---------------------------------------------------------------------------

ha_core = MagicMock()
ha_core.HomeAssistant = MagicMock
ha_core.callback = lambda f: f

ha_config_entries = MagicMock()
ha_config_entries.ConfigEntry = MagicMock

ha_entity_registry = MagicMock()

ha_area_registry = MagicMock()

ha_update_coordinator = MagicMock()
ha_update_coordinator.DataUpdateCoordinator = MagicMock
ha_update_coordinator.CoordinatorEntity = MagicMock

ha_helpers = MagicMock()
ha_helpers.entity_registry = ha_entity_registry
ha_helpers.area_registry = ha_area_registry
ha_helpers.config_validation = MagicMock()
ha_helpers.update_coordinator = ha_update_coordinator

ha = MagicMock()
ha.helpers = ha_helpers
ha.core = ha_core
ha.config_entries = ha_config_entries

sys.modules["homeassistant"] = ha
sys.modules["homeassistant.core"] = ha_core
sys.modules["homeassistant.config_entries"] = ha_config_entries
sys.modules["homeassistant.helpers"] = ha_helpers
sys.modules["homeassistant.helpers.entity_registry"] = ha_entity_registry
sys.modules["homeassistant.helpers.area_registry"] = ha_area_registry
sys.modules["homeassistant.helpers.config_validation"] = ha_helpers.config_validation
sys.modules["homeassistant.helpers.update_coordinator"] = ha_update_coordinator
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["voluptuous"] = MagicMock()

from sunny import services as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockEntityEntry:
    def __init__(self, entity_id, domain, platform):
        self.entity_id = entity_id
        self.domain = domain
        self.platform = platform


def _mock_ent_reg(*entries):
    reg = MagicMock()
    reg.entities = {e.entity_id: e for e in entries}
    return reg


class _MockAreaEntry:
    def __init__(self, area_id, name):
        self.id = area_id
        self.name = name


def _mock_area_reg(*entries: _MockAreaEntry):
    reg = MagicMock()
    by_id = {a.id: a for a in entries}
    by_name = {a.name: a for a in entries}

    def _get_area(area_id):
        return by_id.get(area_id)

    def _get_area_by_name(name):
        return by_name.get(name)

    reg.async_get_area.side_effect = _get_area
    reg.async_get_area_by_name.side_effect = _get_area_by_name
    return reg


def _make_hass():
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    return hass


def _entry(eid, domain="switch", platform="sunny"):
    return _MockEntityEntry(eid, domain, platform)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFindAllAutoControlSwitches:
    def test_returns_sunny_switches_only(self):
        entities = [
            _entry("switch.grand_pilotage_auto"),
            _entry("switch.petit_pilotage_auto"),
            _entry("cover.volet_salon", "cover"),
            _entry("switch.other", "switch", "other_integration"),
        ]
        reg = _mock_ent_reg(*entities)
        ha_entity_registry.async_get = MagicMock(return_value=reg)

        result = svc._find_all_auto_control_switches(MagicMock())

        assert result == {"switch.grand_pilotage_auto", "switch.petit_pilotage_auto"}

    def test_empty_registry(self):
        reg = _mock_ent_reg()
        ha_entity_registry.async_get = MagicMock(return_value=reg)

        result = svc._find_all_auto_control_switches(MagicMock())

        assert result == set()


class TestHandleSetAutoControl:
    @pytest.mark.asyncio
    async def test_enable_all(self):
        hass = _make_hass()
        reg = _mock_ent_reg(
            _entry("switch.grand_pilotage_auto"),
            _entry("switch.petit_pilotage_auto"),
        )
        ha_entity_registry.async_get = MagicMock(return_value=reg)

        call = MagicMock()
        call.data = {"enabled": True}
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        args = hass.services.async_call.call_args
        assert args[0][0] == "switch"
        assert args[0][1] == "turn_on"
        assert set(args[0][2]["entity_id"]) == {"switch.grand_pilotage_auto", "switch.petit_pilotage_auto"}
        assert args[1] == {"context": None}

    @pytest.mark.asyncio
    async def test_disable_all(self):
        hass = _make_hass()
        reg = _mock_ent_reg(_entry("switch.pilotage_auto"))
        ha_entity_registry.async_get = MagicMock(return_value=reg)

        call = MagicMock()
        call.data = {"enabled": False}
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_called_once_with(
            "switch", "turn_off",
            {"entity_id": ["switch.pilotage_auto"]},
            context=None,
        )

    @pytest.mark.asyncio
    async def test_specific_entities(self):
        hass = _make_hass()

        call = MagicMock()
        call.data = {
            "enabled": True,
            "entity_id": ["switch.grand_pilotage_auto"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_called_once_with(
            "switch", "turn_on",
            {"entity_id": ["switch.grand_pilotage_auto"]},
            context=None,
        )

    @pytest.mark.asyncio
    async def test_area_resolution(self):
        hass = _make_hass()
        ha_area_registry.async_get = MagicMock(
            return_value=_mock_area_reg(_MockAreaEntry("uuid_salon", "salon"))
        )
        ha_entity_registry.async_entries_for_area = MagicMock(return_value=[
            _entry("switch.grand_pilotage_auto"),
            _entry("switch.petit_pilotage_auto"),
            _entry("cover.volet", "cover"),
        ])

        call = MagicMock()
        call.data = {
            "enabled": False,
            "area_id": ["salon"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        args = hass.services.async_call.call_args
        entity_ids = set(args[0][2]["entity_id"])
        assert entity_ids == {"switch.grand_pilotage_auto", "switch.petit_pilotage_auto"}
        ha_entity_registry.async_entries_for_area.assert_called_with(
            ha_entity_registry.async_get.return_value, "uuid_salon"
        )

    @pytest.mark.asyncio
    async def test_entity_and_area_union(self):
        hass = _make_hass()
        ha_area_registry.async_get = MagicMock(
            return_value=_mock_area_reg(_MockAreaEntry("uuid_salon", "salon"))
        )
        ha_entity_registry.async_entries_for_area = MagicMock(return_value=[
            _entry("switch.grand_pilotage_auto"),
        ])

        call = MagicMock()
        call.data = {
            "enabled": True,
            "entity_id": ["switch.petit_pilotage_auto"],
            "area_id": ["salon"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        args = hass.services.async_call.call_args
        entity_ids = set(args[0][2]["entity_id"])
        assert entity_ids == {"switch.grand_pilotage_auto", "switch.petit_pilotage_auto"}

    @pytest.mark.asyncio
    async def test_no_entities_noop(self):
        hass = _make_hass()
        ha_entity_registry.async_get = MagicMock(return_value=_mock_ent_reg())

        call = MagicMock()
        call.data = {"enabled": True}
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_area_no_entities(self):
        hass = _make_hass()
        ha_area_registry.async_get = MagicMock(
            return_value=_mock_area_reg(_MockAreaEntry("uuid_vide", "vide"))
        )
        ha_entity_registry.async_entries_for_area = MagicMock(return_value=[])
        ha_entity_registry.async_get = MagicMock(return_value=_mock_ent_reg())

        call = MagicMock()
        call.data = {
            "enabled": True,
            "area_id": ["vide"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_area_resolution_by_uuid(self):
        hass = _make_hass()
        ha_area_registry.async_get = MagicMock(
            return_value=_mock_area_reg(_MockAreaEntry("uuid_salon", "salon"))
        )
        ha_entity_registry.async_entries_for_area = MagicMock(return_value=[
            _entry("switch.grand_pilotage_auto"),
        ])

        call = MagicMock()
        call.data = {
            "enabled": True,
            "area_id": ["uuid_salon"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        ha_entity_registry.async_entries_for_area.assert_called_with(
            ha_entity_registry.async_get.return_value, "uuid_salon"
        )

    @pytest.mark.asyncio
    async def test_area_resolution_unknown_name_skipped(self):
        hass = _make_hass()
        ha_area_registry.async_get = MagicMock(
            return_value=_mock_area_reg()
        )
        ha_entity_registry.async_entries_for_area = MagicMock()
        ha_entity_registry.async_get = MagicMock(
            return_value=_mock_ent_reg(
                _entry("switch.pilotage_auto"),
            )
        )

        call = MagicMock()
        call.data = {
            "enabled": True,
            "area_id": ["zone_inconnue"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        ha_entity_registry.async_entries_for_area.assert_not_called()
        args = hass.services.async_call.call_args
        assert set(args[0][2]["entity_id"]) == {"switch.pilotage_auto"}

    @pytest.mark.asyncio
    async def test_passes_context(self):
        hass = _make_hass()
        reg = _mock_ent_reg(_entry("switch.pilotage_auto"))
        ha_entity_registry.async_get = MagicMock(return_value=reg)

        ctx = MagicMock()
        call = MagicMock()
        call.data = {"enabled": True}
        call.context = ctx
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_called_once()
        assert hass.services.async_call.call_args[1]["context"] is ctx


class TestRegisterServices:
    def test_registers_when_not_present(self):
        hass = _make_hass()
        hass.services.has_service.return_value = False

        svc.async_register_services(hass)

        hass.services.async_register.assert_called_once()
        call_args = hass.services.async_register.call_args[0]
        assert call_args[0] == "sunny"
        assert call_args[1] == "set_auto_control"

    def test_skips_when_already_registered(self):
        hass = _make_hass()
        hass.services.has_service.return_value = True

        svc.async_register_services(hass)

        hass.services.async_register.assert_not_called()