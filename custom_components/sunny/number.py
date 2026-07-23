"""Plateforme number pour les bornes min/max de position."""

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_entity_registry_updated_event
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


class SunnyBasePositionNumber(CoordinatorEntity, NumberEntity):
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