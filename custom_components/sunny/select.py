"""Plateforme select pour l'intégration Sunny."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunnyCoordinator, _window_key
from .sensor import fallback_device_info, resolve_cover_device
from .strategies import STRATEGY_OPTIONS


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
        window_id = _window_key(win, idx)

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
            SunnyStrategySelect(coordinator, name, idx, window_id, device_info)
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


class SunnyStrategySelect(CoordinatorEntity, SelectEntity):
    """Select pour changer la stratégie d'un store."""

    _attr_icon = "mdi:cog-outline"
    _attr_has_entity_name = True

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
        self._window_id = window_id
        # cover_entity capturé à la construction (index encore valide) pour
        # retrouver la fenêtre si l'index positionnel devient obsolète.
        self._cover_entity = ""
        _windows = coordinator.entry.options.get("windows", [])
        if 0 <= window_idx < len(_windows):
            self._cover_entity = _windows[window_idx].get("cover_entity", "")
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{window_id}_{window_name}_strategy_select"
        )
        self._attr_device_info = device_info
        self._attr_name = f"{window_name} Choix stratégie"

    def _resolve_window_index(self, windows: list[dict]) -> int | None:
        """Index courant de la fenêtre : cover_entity → id → index positionnel."""
        if self._cover_entity:
            for i, w in enumerate(windows):
                if w.get("cover_entity") == self._cover_entity:
                    return i
        if self._window_id:
            for i, w in enumerate(windows):
                if w.get("id") == self._window_id:
                    return i
        return self._window_idx if 0 <= self._window_idx < len(windows) else None

    @property
    def options(self) -> list[str]:
        return list(STRATEGY_OPTIONS.keys())

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data.get(self._window_id)
        if data is None:
            return None
        return data.get("strategy")

    async def async_select_option(self, option: str) -> None:
        new_options = dict(self.coordinator.entry.options)
        windows = list(new_options.get("windows", []))
        idx = self._resolve_window_index(windows)
        if idx is not None:
            windows[idx] = dict(windows[idx])
            windows[idx]["strategy"] = option
        new_options["windows"] = windows
        self.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        self.coordinator.entry = self.hass.config_entries.async_get_entry(
            self.coordinator.entry.entry_id
        )
        await self.coordinator.async_request_refresh()