"""Tests unitaires pour _resolve_lux_sensors et _compute_lux_target_position du coordinateur."""

import sys
from datetime import datetime, timedelta, timezone
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

def _make_mock_entity(entity_id, domain, area_id, device_class, original_device_class, disabled, device_id=None):
    """Crée un mock EntityEntry."""
    entity = MagicMock()
    entity.entity_id = entity_id
    entity.domain = domain
    entity.area_id = area_id
    entity.device_class = device_class
    entity.original_device_class = original_device_class
    entity.disabled = disabled
    entity.device_id = device_id
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

    def test_finds_sensor_via_device_area(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.z2m_lux", "sensor", None,
            device_class=None, original_device_class="illuminance", disabled=False,
            device_id="dev_abcd1234",
        )
        ent_reg = _mock_entity_registry([entity])

        device = MagicMock()
        device.area_id = "salon"

        dev_reg = MagicMock()
        dev_reg.async_get.return_value = device

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            with patch.object(coordinator_module.dr, "async_get", return_value=dev_reg):
                result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == ["sensor.z2m_lux"]

    def test_entity_with_neither_area_nor_device_area(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.z2m_lux", "sensor", None,
            device_class=None, original_device_class="illuminance", disabled=False,
            device_id="dev_abcd1234",
        )
        ent_reg = _mock_entity_registry([entity])

        device = MagicMock()
        device.area_id = None

        dev_reg = MagicMock()
        dev_reg.async_get.return_value = device

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            with patch.object(coordinator_module.dr, "async_get", return_value=dev_reg):
                result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == []

    def test_entity_area_takes_priority_over_device_area(self, coordinator_instance, mock_hass):
        entity = _make_mock_entity(
            "sensor.z2m_lux", "sensor", "salon",
            device_class=None, original_device_class="illuminance", disabled=False,
            device_id="dev_abcd1234",
        )
        ent_reg = _mock_entity_registry([entity])

        device = MagicMock()
        device.area_id = "bureau"

        dev_reg = MagicMock()
        dev_reg.async_get.return_value = device

        with patch.object(coordinator_module.er, "async_get", return_value=ent_reg):
            with patch.object(coordinator_module.dr, "async_get", return_value=dev_reg):
                result = coordinator_instance._resolve_lux_sensors({"lux_area_id": "salon"})
        assert result == ["sensor.z2m_lux"]


# ---------------------------------------------------------------------------
# Tests _compute_lux_target_position — stale detection
# ---------------------------------------------------------------------------

def _make_mock_state(state_value, last_changed, last_updated, attributes=None):
    """Crée un mock State."""
    st = MagicMock()
    st.state = state_value
    st.last_changed = last_changed
    st.last_updated = last_updated
    st.attributes = attributes or {}
    return st


class TestComputeLuxTargetStale:
    """Tests pour la détection stale dans _compute_lux_target_position."""

    NOW = datetime(2026, 7, 25, 18, 40, 0, tzinfo=timezone.utc)

    def test_sensor_used_when_cover_moved_over_60s_ago(self, coordinator_instance, mock_hass):
        cover_last_changed = self.NOW - timedelta(seconds=120)
        sensor_last_updated = self.NOW - timedelta(hours=4)

        cover_state = _make_mock_state("open", cover_last_changed, cover_last_changed, {"current_position": 31})
        sensor_state = _make_mock_state("0", sensor_last_updated, sensor_last_updated, {"device_class": "illuminance"})

        mock_hass.states.get.side_effect = lambda eid: {
            "cover.test": cover_state,
            "sensor.lux_salon": sensor_state,
        }.get(eid)

        win = {
            "cover_entity": "cover.test",
            "lux_sensors": ["sensor.lux_salon"],
            "lux_high": 5000,
            "lux_low": 3000,
            "lux_step": 10,
        }

        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        with patch("sunny.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = self.NOW
            mock_dt.timezone = timezone
            mock_dt.timedelta = timedelta
            result = coordinator_instance._compute_lux_target_position(win, strategy)
        assert result == 41  # lux=0 < 3000 → ouvert: 31 + 10 = 41

    def test_sensor_stale_when_cover_moved_under_60s_ago(self, coordinator_instance, mock_hass):
        cover_last_changed = self.NOW - timedelta(seconds=30)
        sensor_last_updated = self.NOW - timedelta(hours=4)

        cover_state = _make_mock_state("open", cover_last_changed, cover_last_changed, {"current_position": 31})
        sensor_state = _make_mock_state("0", sensor_last_updated, sensor_last_updated, {"device_class": "illuminance"})

        mock_hass.states.get.side_effect = lambda eid: {
            "cover.test": cover_state,
            "sensor.lux_salon": sensor_state,
        }.get(eid)

        win = {
            "cover_entity": "cover.test",
            "lux_sensors": ["sensor.lux_salon"],
            "lux_high": 5000,
            "lux_low": 3000,
            "lux_step": 10,
        }

        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        with patch("sunny.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = self.NOW
            mock_dt.timezone = timezone
            mock_dt.timedelta = timedelta
            result = coordinator_instance._compute_lux_target_position(win, strategy)

        assert result == 31  # stale → position inchangée

    def test_sensor_stale_at_exactly_60s_boundary(self, coordinator_instance, mock_hass):
        cover_last_changed = self.NOW - timedelta(seconds=60)
        sensor_last_updated = self.NOW - timedelta(hours=4)

        cover_state = _make_mock_state("open", cover_last_changed, cover_last_changed, {"current_position": 31})
        sensor_state = _make_mock_state("0", sensor_last_updated, sensor_last_updated, {"device_class": "illuminance"})

        mock_hass.states.get.side_effect = lambda eid: {
            "cover.test": cover_state,
            "sensor.lux_salon": sensor_state,
        }.get(eid)

        win = {
            "cover_entity": "cover.test",
            "lux_sensors": ["sensor.lux_salon"],
            "lux_high": 5000,
            "lux_low": 3000,
            "lux_step": 10,
        }

        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        with patch("sunny.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = self.NOW
            mock_dt.timezone = timezone
            mock_dt.timedelta = timedelta
            result = coordinator_instance._compute_lux_target_position(win, strategy)

        assert result == 41  # 60s exact → pas stale → ouvert: 31 + 10 = 41


# ---------------------------------------------------------------------------
# Tests _compute_lux_target_position — snapshot stable pendant le mouvement
# ---------------------------------------------------------------------------

class TestComputeLuxTargetPreviousDesired:
    """Régression : fallback sur la position désirée précédente.

    lux_target calcule la position à partir de la position courante du
    volet. Si un rafraîchissement tombe pendant le mouvement (ou la grâce
    de 60s), le snapshot `desired_position` stocké ne correspond plus à la
    position d'arrêt et le switch désactive le pilotage auto à tort.
    """

    NOW = datetime(2026, 7, 25, 18, 40, 0, tzinfo=timezone.utc)

    def _win(self, sensors):
        return {
            "name": "Salon",
            "cover_entity": "cover.test",
            "lux_sensors": sensors,
            "lux_high": 5000,
            "lux_low": 3000,
            "lux_step": 10,
        }

    def _states(self, mock_hass, cover_state_value, cover_last_changed, current_position, sensor_state=None):
        cover_state = _make_mock_state(
            cover_state_value, cover_last_changed, cover_last_changed,
            {"current_position": current_position},
        )
        mapping = {"cover.test": cover_state}
        if sensor_state is not None:
            mapping["sensor.lux_salon"] = sensor_state
        mock_hass.states.get.side_effect = lambda eid: mapping.get(eid)

    def _stale_sensor(self):
        sensor_last_updated = self.NOW - timedelta(hours=4)
        return _make_mock_state(
            "0", sensor_last_updated, sensor_last_updated,
            {"device_class": "illuminance"},
        )

    def _compute(self, coordinator_instance, win, strategy):
        with patch("sunny.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = self.NOW
            mock_dt.timezone = timezone
            mock_dt.timedelta = timedelta
            return coordinator_instance._compute_lux_target_position(win, strategy)

    def test_stale_returns_previous_desired(self, coordinator_instance, mock_hass):
        cover_last_changed = self.NOW - timedelta(seconds=30)
        self._states(mock_hass, "open", cover_last_changed, 31, self._stale_sensor())
        coordinator_instance.data = {"Salon": {"desired_position": 90}}
        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        result = self._compute(coordinator_instance, self._win(["sensor.lux_salon"]), strategy)

        assert result == 90  # stale → conserve la position désirée précédente

    def test_stale_without_previous_data_returns_current_position(self, coordinator_instance, mock_hass):
        cover_last_changed = self.NOW - timedelta(seconds=30)
        self._states(mock_hass, "open", cover_last_changed, 31, self._stale_sensor())
        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        result = self._compute(coordinator_instance, self._win(["sensor.lux_salon"]), strategy)

        assert result == 31  # pas de snapshot précédent → repli sur la position courante

    def test_cover_moving_returns_previous_desired(self, coordinator_instance, mock_hass):
        """Volet en mouvement : la position instantanée n'est pas fiable."""
        sensor_last_updated = self.NOW - timedelta(hours=4)
        sensor_state = _make_mock_state(
            "0", sensor_last_updated, sensor_last_updated,
            {"device_class": "illuminance"},
        )
        self._states(mock_hass, "opening", self.NOW, 95, sensor_state)
        coordinator_instance.data = {"Salon": {"desired_position": 90}}
        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        result = self._compute(coordinator_instance, self._win(["sensor.lux_salon"]), strategy)

        assert result == 90  # volet en mouvement → conserve le snapshot précédent

    def test_no_sensors_returns_previous_desired(self, coordinator_instance, mock_hass):
        cover_last_changed = self.NOW - timedelta(hours=2)
        self._states(mock_hass, "open", cover_last_changed, 31)
        coordinator_instance.data = {"Salon": {"desired_position": 90}}
        strategy = MagicMock()
        strategy.compute_position.return_value = 41

        result = self._compute(coordinator_instance, self._win([]), strategy)

        assert result == 90

# ---------------------------------------------------------------------------
# Tests _merge_sensor_groups
# ---------------------------------------------------------------------------

class TestMergeSensorGroups:
    """Tests pour le regroupement par capteurs résolus partagés."""

    def test_no_intersection_separate(self):
        resolved = {"Grand": {"s1"}, "Cuisine": {"s2"}}
        assert coordinator_module._merge_sensor_groups(resolved) == [["Grand"], ["Cuisine"]]

    def test_shared_sensor_merged(self):
        """Salon (area) + cuisine (manuelle) résolvent la même entité → même groupe."""
        resolved = {"Grand": {"sensor.salon_lux"}, "Cuisine": {"sensor.salon_lux"}}
        assert coordinator_module._merge_sensor_groups(resolved) == [["Grand", "Cuisine"]]

    def test_chained_merge(self):
        resolved = {"A": {"s1"}, "B": {"s1", "s2"}, "C": {"s2"}}
        groups = coordinator_module._merge_sensor_groups(resolved)
        assert sorted(groups) == [["A", "B", "C"]]

    def test_empty_sensors_never_merge(self):
        resolved = {"A": set(), "B": set()}
        assert coordinator_module._merge_sensor_groups(resolved) == [["A"], ["B"]]


# ---------------------------------------------------------------------------
# Tests _resolve_lux_context
# ---------------------------------------------------------------------------

class TestResolveLuxContext:
    """Tests pour la résolution du contexte lux (refactor de _compute_lux_target_position)."""

    NOW = datetime(2026, 7, 25, 18, 40, 0, tzinfo=timezone.utc)

    def _states(self, mock_hass, cover_position, cover_state_value="open", sensor_lux="0"):
        cover_last_changed = self.NOW - timedelta(hours=2)
        cover_state = _make_mock_state(
            cover_state_value, cover_last_changed, cover_last_changed,
            {"current_position": cover_position},
        )
        mapping = {"cover.test": cover_state}
        if sensor_lux is not None:
            sensor_last_updated = self.NOW - timedelta(hours=4)
            mapping["sensor.lux_salon"] = _make_mock_state(
                sensor_lux, sensor_last_updated, sensor_last_updated,
                {"device_class": "illuminance"},
            )
        mock_hass.states.get.side_effect = lambda eid: mapping.get(eid)

    def _compute(self, coordinator_instance, win):
        with patch("sunny.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = self.NOW
            mock_dt.timezone = timezone
            mock_dt.timedelta = timedelta
            return coordinator_instance._resolve_lux_context(win)

    def test_fresh_lux_with_sensors(self, coordinator_instance, mock_hass):
        self._states(mock_hass, cover_position=50, sensor_lux="4000")
        win = {"name": "Salon", "cover_entity": "cover.test",
               "lux_sensors": ["sensor.lux_salon"]}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["lux"] == 4000.0
        assert ctx["current_position"] == 50
        assert ctx["sensors"] == {"sensor.lux_salon"}

    def test_no_sensors_lux_none(self, coordinator_instance, mock_hass):
        self._states(mock_hass, cover_position=50, sensor_lux=None)
        win = {"name": "Salon", "cover_entity": "cover.test", "lux_sensors": []}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["lux"] is None
        assert ctx["sensors"] == set()

    def test_moving_cover_lux_none_and_previous_fallback(self, coordinator_instance, mock_hass):
        sensor_last_updated = self.NOW - timedelta(hours=4)
        sensor_state = _make_mock_state(
            "0", sensor_last_updated, sensor_last_updated, {"device_class": "illuminance"},
        )
        cover_state = _make_mock_state("opening", self.NOW, self.NOW, {"current_position": 95})
        mock_hass.states.get.side_effect = lambda eid: {
            "cover.test": cover_state, "sensor.lux_salon": sensor_state,
        }.get(eid)
        coordinator_instance.data = {"Salon": {"desired_position": 90}}
        win = {"name": "Salon", "cover_entity": "cover.test",
               "lux_sensors": ["sensor.lux_salon"]}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["lux"] is None
        assert ctx["fallback"] == 90

    def test_no_previous_data_fallback_is_current(self, coordinator_instance, mock_hass):
        self._states(mock_hass, cover_position=50, sensor_lux=None)
        coordinator_instance.data = {}
        win = {"name": "Salon", "cover_entity": "cover.test", "lux_sensors": []}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["fallback"] == 50
