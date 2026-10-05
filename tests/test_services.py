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
        reg = _mock_ent_reg(_entry("switch.grand_pilotage_auto"))
        reg.async_get.side_effect = lambda eid: reg.entities.get(eid)
        ha_entity_registry.async_get = MagicMock(return_value=reg)

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
        reg = _mock_ent_reg(_entry("switch.petit_pilotage_auto"))
        reg.async_get.side_effect = lambda eid: reg.entities.get(eid)
        ha_entity_registry.async_get = MagicMock(return_value=reg)
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


# ---------------------------------------------------------------------------
# Tests filtrage des entity_id fournis explicitement
# ---------------------------------------------------------------------------

class TestFilterProvidedEntityIds:
    """Régression : les entity_id fournis doivent être filtrés sur les
    switches Sunny du registre, avec un warning pour les ignorés (sinon
    les cibles obsolètes disparaissent en silence)."""

    def _registry(self, *entries):
        reg = _mock_ent_reg(*entries)
        reg.async_get.side_effect = lambda eid: reg.entities.get(eid)
        return reg

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_entities_filtered(self):
        hass = _make_hass()
        ha_entity_registry.async_get = MagicMock(return_value=self._registry(
            _entry("switch.sunny_a"),
            _entry("switch.other", "switch", "other_integration"),
            _entry("cover.volet", "cover"),
        ))

        call = MagicMock()
        call.data = {
            "enabled": True,
            "entity_id": ["switch.sunny_a", "switch.other", "switch.ghost"],
        }
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        args = hass.services.async_call.call_args
        assert set(args[0][2]["entity_id"]) == {"switch.sunny_a"}

    @pytest.mark.asyncio
    async def test_no_valid_target_no_fallback_to_all(self):
        """Des cibles explicites toutes invalides ne doivent PAS retomber
        sur « tous les switches » : avertissement et no-op."""
        hass = _make_hass()
        ha_entity_registry.async_get = MagicMock(return_value=self._registry(
            _entry("switch.sunny_a"),
        ))

        call = MagicMock()
        call.data = {"enabled": True, "entity_id": ["switch.ghost"]}
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_explicit_target_forwarded(self):
        hass = _make_hass()
        ha_entity_registry.async_get = MagicMock(return_value=self._registry(
            _entry("switch.sunny_a"),
        ))

        call = MagicMock()
        call.data = {"enabled": True, "entity_id": ["switch.sunny_a"]}
        call.context = None
        await svc._handle_set_auto_control(hass, call)

        hass.services.async_call.assert_called_once_with(
            "switch", "turn_on",
            {"entity_id": ["switch.sunny_a"]},
            context=None,
        )


class TestHandleRefresh:
    @pytest.mark.asyncio
    async def test_refreshes_all_coordinators(self):
        hass = _make_hass()
        co1 = MagicMock()
        co1.async_refresh = AsyncMock()
        co2 = MagicMock()
        co2.async_refresh = AsyncMock()
        hass.data = {svc.DOMAIN: {"entry1": co1, "entry2": co2}}

        call = MagicMock()
        call.data = {}
        call.hass = hass
        await svc._handle_refresh(call)

        co1.async_refresh.assert_awaited_once()
        co2.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_entries_noop(self):
        hass = _make_hass()
        hass.data = {}

        call = MagicMock()
        call.data = {}
        call.hass = hass
        await svc._handle_refresh(call)


class TestRegisterServices:
    def test_registers_when_not_present(self):
        hass = _make_hass()
        hass.services.has_service.return_value = False

        svc.async_register_services(hass)

        registered = [c[0][:2] for c in hass.services.async_register.call_args_list]
        assert ("sunny", "set_auto_control") in registered
        assert ("sunny", "refresh") in registered
        assert ("sunny", "set_cloud_factor") in registered
        assert len(registered) == 3

    @pytest.mark.asyncio
    async def test_refresh_handler_called_with_call_only(self):
        """Régression : HA appelle le handler avec ServiceCall seul, pas (hass, call)."""
        hass = _make_hass()
        hass.services.has_service.return_value = False
        co = MagicMock()
        co.async_refresh = AsyncMock()
        hass.data = {svc.DOMAIN: {"entry1": co}}

        svc.async_register_services(hass)

        handlers = [
            c[0][2] for c in hass.services.async_register.call_args_list
            if c[0][1] == "refresh"
        ]
        assert len(handlers) == 1

        call = MagicMock()
        call.data = {}
        call.hass = hass
        await handlers[0](call)

        co.async_refresh.assert_awaited_once()

    def test_skips_when_already_registered(self):
        hass = _make_hass()
        hass.services.has_service.return_value = True

        svc.async_register_services(hass)

        hass.services.async_register.assert_not_called()


class TestHandleSetCloudFactor:
    @pytest.mark.asyncio
    async def test_updates_all_entries_and_refreshes(self):
        hass = _make_hass()
        coordinators = {}
        for eid, current in [("entry1", 0.0), ("entry2", 50.0)]:
            coord = MagicMock()
            entry = MagicMock()
            entry.entry_id = eid
            entry.options = {"cloud_factor": current, "windows": []}
            coord.entry = entry
            coord.async_request_refresh = AsyncMock()
            coordinators[eid] = coord
        hass.data = {svc.DOMAIN: coordinators}

        def _update(entry, options=None, **kwargs):
            entry.options = options
            return True

        hass.config_entries.async_update_entry.side_effect = _update
        hass.config_entries.async_get_entry.side_effect = (
            lambda eid: coordinators[eid].entry
        )

        call = MagicMock()
        call.data = {"value": 100.0}
        await svc._handle_set_cloud_factor(hass, call)

        assert coordinators["entry1"].entry.options["cloud_factor"] == 100.0
        assert coordinators["entry2"].entry.options["cloud_factor"] == 100.0
        for coord in coordinators.values():
            coord.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_entries_is_noop(self):
        hass = _make_hass()
        hass.data = {}

        call = MagicMock()
        call.data = {"value": 10.0}
        await svc._handle_set_cloud_factor(hass, call)

        hass.config_entries.async_update_entry.assert_not_called()