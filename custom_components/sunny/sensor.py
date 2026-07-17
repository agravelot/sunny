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
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunnyCoordinator
from .strategies import STRATEGIES

_LOGGER = logging.getLogger(__name__)


def fallback_device_info(entry: ConfigEntry, window_name: str) -> DeviceInfo:
    """Crée un DeviceInfo Sunny dédié (fallback)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{window_name}")},
        name=window_name,
        manufacturer="Sunny",
        model="Gestion solaire de store",
    )


async def resolve_cover_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    cover_entity_id: str,
    window_name: str,
) -> DeviceInfo | None:
    """Résout le DeviceInfo en se liant au device du cover s'il existe.

    Retourne None si le cover n'est pas encore dans l'entity_registry
    (la création des entités Sunny sera différée).
    """
    ent_reg = er.async_get(hass)

    entity_entry = ent_reg.async_get(cover_entity_id)
    if not entity_entry:
        return None

    dev_reg = dr.async_get(hass)

    if not entity_entry.device_id:
        _LOGGER.info(
            "Entité '%s' sans device_id dans l'entity_registry",
            cover_entity_id,
        )
        return fallback_device_info(entry, window_name)

    device = dev_reg.async_get(entity_entry.device_id)
    if not device:
        _LOGGER.info(
            "Device '%s' introuvable dans le device_registry pour l'entité '%s'",
            entity_entry.device_id,
            cover_entity_id,
        )
        return fallback_device_info(entry, window_name)

    if not device.identifiers:
        _LOGGER.info(
            "Device '%s' sans identifiers pour l'entité '%s'",
            device.name or entity_entry.device_id,
            cover_entity_id,
        )
        return fallback_device_info(entry, window_name)

    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=device.identifiers,
    )

    return DeviceInfo(identifiers=device.identifiers)


def _create_window_entities(
    coordinator: SunnyCoordinator,
    window_name: str,
    window_id: str,
    device_info: DeviceInfo,
) -> list[SunnyBaseSensor]:
    """Crée les 4 entités capteur pour une fenêtre."""
    return [
        SunnySunSensor(coordinator, window_name, window_id, device_info),
        SunnyPositionSensor(coordinator, window_name, window_id, device_info),
        SunnyStrategySensor(coordinator, window_name, window_id, device_info),
        SunnyCloudSensor(coordinator, window_name, window_id, device_info),
    ]


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

        if cover_entity_id:
            device_info = await resolve_cover_device(
                hass, entry, cover_entity_id, name
            )
            if device_info is None:
                pending_covers.add(cover_entity_id)
                continue
        else:
            device_info = fallback_device_info(entry, name)

        window_id = win.get("id", win.get("cover_entity", str(idx)))
        entities.extend(_create_window_entities(coordinator, name, window_id, device_info))

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


class SunnyBaseSensor(CoordinatorEntity, SensorEntity):
    """Classe de base commune à tous les capteurs Sunny."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_id: str,
        device_info: DeviceInfo,
        sensor_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._window_id = window_id
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{window_id}_{window_name}_{sensor_type}"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class SunnySunSensor(SunnyBaseSensor):
    """Capteur d'ensoleillement direct (% de la fenêtre éclairée)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-wireless"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, window_id, device_info, "sun")
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
        window_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, window_id, device_info, "position")
        self._attr_name = f"{window_name} Position désirée"

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return

        self._attr_native_value = data.get("desired_position", 100)
        self._attr_extra_state_attributes = {
            "cover_entity": data.get("cover_entity"),
            "tilt_threshold": data.get("tilt_threshold"),
            "slat_transmission": data.get("slat_transmission"),
        }
        self.async_write_ha_state()


class SunnyStrategySensor(SunnyBaseSensor):
    """Capteur de stratégie active."""

    _attr_icon = "mdi:cog-outline"

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, window_id, device_info, "strategy")
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
        window_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, window_name, window_id, device_info, "cloud")
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