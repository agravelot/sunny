"""Plateforme select pour l'intégration Sunny."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunnyCoordinator
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
    for idx, win in enumerate(windows):
        name = win["name"]
        cover_entity_id = win.get("cover_entity", "")
        if cover_entity_id:
            device_info = await resolve_cover_device(
                hass, entry, cover_entity_id, name
            )
        else:
            device_info = fallback_device_info(entry, name)
        entities.append(
            SunnyStrategySelect(coordinator, name, idx, device_info)
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
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._window_idx = window_idx
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{window_name}_strategy_select"
        )
        self._attr_device_info = device_info
        self._attr_name = f"{window_name} Choix stratégie"

    @property
    def options(self) -> list[str]:
        return list(STRATEGY_OPTIONS.keys())

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return None
        return data.get("strategy")

    async def async_select_option(self, option: str) -> None:
        new_options = dict(self.coordinator.entry.options)
        windows = list(new_options.get("windows", []))
        if 0 <= self._window_idx < len(windows):
            windows[self._window_idx]["strategy"] = option
        new_options["windows"] = windows
        await self.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        self.coordinator.entry = self.hass.config_entries.async_get_entry(
            self.coordinator.entry.entry_id
        )
        await self.coordinator.async_request_refresh()