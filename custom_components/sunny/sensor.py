"""Plateforme capteur pour l'intégration Sunny."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunnyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SunnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    windows = entry.options.get("windows", [])
    async_add_entities(
        SunnyWindowSensor(coordinator, win["name"])
        for win in windows
    )


class SunnyWindowSensor(CoordinatorEntity, SensorEntity):
    """Capteur d'ensoleillement pour une fenêtre."""

    _attr_has_entity_name = True
    _attr_translation_key = "window"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-wireless"

    def __init__(self, coordinator: SunnyCoordinator, window_name: str) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{window_name}"
        self._attr_translation_placeholders = {"window": window_name}
        self._attr_name = window_name

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return

        self._attr_native_value = data.get("lit_pct", 0.0)
        self._attr_extra_state_attributes = {
            "solar_altitude": data.get("solar_altitude"),
            "solar_azimuth": data.get("solar_azimuth"),
            "gamma": data.get("gamma"),
            "hp": data.get("hp"),
            "theta": data.get("theta"),
            "behind": data.get("behind"),
            "d_lat": data.get("d_lat"),
            "d_vert": data.get("d_vert"),
            "lit_area_m2": data.get("lit_area_m2"),
            "screen_blocks_all": data.get("screen_blocks_all"),
            "horizon_dip": data.get("horizon_dip"),
            "cloud_coverage": data.get("cloud_coverage"),
            "weather_condition": data.get("weather_condition"),
            "temperature": data.get("temperature"),
            "cover_entity": data.get("cover_entity"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
        self.async_write_ha_state()