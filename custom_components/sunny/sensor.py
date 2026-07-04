"""Plateforme capteur pour l'intégration Sunny."""

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunnyCoordinator
from .strategies import STRATEGIES

_LOGGER = logging.getLogger(__name__)


def _resolve_cover_device_info(
    hass: HomeAssistant,
    entry: ConfigEntry,
    cover_entity_id: str,
    window_name: str,
) -> DeviceInfo:
    """Résout le DeviceInfo en se liant au device du cover s'il existe."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    entity_entry = ent_reg.async_get(cover_entity_id)
    if entity_entry and entity_entry.device_id:
        device = dev_reg.async_get(entity_entry.device_id)
        if device and device.identifiers:
            return DeviceInfo(identifiers=device.identifiers)

    _LOGGER.debug(
        "Cover '%s' sans device, création d'un device Sunny dédié pour '%s'",
        cover_entity_id,
        window_name,
    )
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{window_name}")},
        name=window_name,
        manufacturer="Sunny",
        model="Gestion solaire de store",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SunnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    windows = entry.options.get("windows", [])

    entities = []
    for win in windows:
        name = win["name"]
        cover_entity_id = win.get("cover_entity", "")
        if cover_entity_id:
            device_info = _resolve_cover_device_info(
                hass, entry, cover_entity_id, name
            )
        else:
            device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{name}")},
                name=name,
                manufacturer="Sunny",
                model="Gestion solaire de store",
            )
        entities.extend([
            SunnySunSensor(coordinator, name, device_info),
            SunnyPositionSensor(coordinator, name, device_info),
            SunnyStrategySensor(coordinator, name, device_info),
            SunnyCloudSensor(coordinator, name, device_info),
        ])

    async_add_entities(entities)


class SunnyBaseSensor(CoordinatorEntity, SensorEntity):
    """Classe de base commune à tous les capteurs Sunny."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        device_info: DeviceInfo,
        sensor_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{window_name}_{sensor_type}"
        self._attr_device_info = device_info


class SunnySunSensor(SunnyBaseSensor):
    """Capteur d'ensoleillement direct (% de la fenêtre éclairée)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-wireless"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, device_info, "sun")
        self._attr_name = f"{window_name} Ensoleillement"

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
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
        self.async_write_ha_state()


class SunnyPositionSensor(SunnyBaseSensor):
    """Capteur de position désirée du store (%)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:blinds"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, device_info, "position")
        self._attr_name = f"{window_name} Position désirée"

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return

        self._attr_native_value = data.get("desired_position", 100)
        self._attr_extra_state_attributes = {
            "cover_entity": data.get("cover_entity"),
        }
        self.async_write_ha_state()


class SunnyStrategySensor(SunnyBaseSensor):
    """Capteur de stratégie active."""

    _attr_icon = "mdi:cog-outline"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, device_info, "strategy")
        self._attr_name = f"{window_name} Stratégie"

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return

        strategy_name = data.get("strategy", "")
        strategy = STRATEGIES.get(strategy_name)
        self._attr_native_value = strategy.label if strategy else strategy_name
        self.async_write_ha_state()


class SunnyCloudSensor(SunnyBaseSensor):
    """Capteur de couverture nuageuse (%)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weather-cloudy"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, device_info, "cloud")
        self._attr_name = f"{window_name} Couverture nuageuse"

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return

        self._attr_native_value = data.get("cloud_coverage")
        self._attr_extra_state_attributes = {
            "weather_condition": data.get("weather_condition"),
            "temperature": data.get("temperature"),
        }
        self.async_write_ha_state()