"""Coordinateur de données pour l'intégration Sunny."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_STRATEGY_HIGH,
    DEFAULT_STRATEGY_LOW,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_LIT_THRESHOLD,
    DEFAULT_TARGET_ILLUMINATION,
)
from .solar_math import compute_window
from .strategies import get_strategy

_LOGGER = logging.getLogger(__name__)


class SunnyCoordinator(DataUpdateCoordinator):
    """Coordinateur qui recalcule l'ensoleillement périodiquement."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
        )
        self.entry = entry

    async def _async_update_data(self) -> dict:
        sun = self.hass.states.get("sun.sun")
        if sun is None:
            _LOGGER.warning("Entité sun.sun introuvable")
            return self.data if self.data else {}

        h = sun.attributes.get("elevation")
        As = sun.attributes.get("azimuth")
        if h is None or As is None:
            _LOGGER.warning("sun.sun sans elevation ou azimuth")
            return self.data if self.data else {}

        weather_data = {"cloud_coverage": None, "weather_condition": None, "temperature": None}
        weather_entity = (
            self.entry.options.get("weather_entity")
            or self.entry.data.get("weather_entity")
        )
        if weather_entity:
            weather = self.hass.states.get(weather_entity)
            if weather is None:
                _LOGGER.warning("Entité météo '%s' introuvable", weather_entity)
            else:
                weather_data["cloud_coverage"] = weather.attributes.get("cloud_coverage")
                weather_data["weather_condition"] = weather.state
                weather_data["temperature"] = weather.attributes.get("temperature")

        results = {}
        windows = self.entry.options.get("windows", [])
        for idx, win in enumerate(windows):
            name = win.get("name", "Fenêtre")
            lat = win.get("latitude", self.hass.config.latitude)
            lon = win.get("longitude", self.hass.config.longitude)
            zone_entity = win.get("zone_entity")
            if zone_entity:
                zone = self.hass.states.get(zone_entity)
                if zone is None:
                    _LOGGER.warning("Entité zone '%s' introuvable pour la fenêtre '%s'", zone_entity, name)
                else:
                    lat = zone.attributes.get("latitude", lat)
                    lon = zone.attributes.get("longitude", lon)
            orientation = win.get("orientation", 180)
            width = win.get("width", 1.2)
            height = win.get("height", 1.4)
            wall = win.get("wall_thickness", 0.25)
            obstacles = win.get("obstacles", [])
            alt = win.get("altitude", 10)
            ground_alt = win.get("ground_altitude", 208)

            try:
                data = compute_window(
                    h=h, As=As, An=orientation,
                    W=width, Hw=height, e=wall,
                    obstacles=obstacles, altitude=alt,
                    ground_altitude=ground_alt,
                )
            except Exception:
                _LOGGER.exception(
                    "Erreur lors du calcul solaire pour la fenêtre '%s'",
                    name,
                )
                continue
            data["cover_entity"] = win.get("cover_entity")
            data["zone_entity"] = win.get("zone_entity")
            data["tilt_threshold"] = win.get("tilt_threshold", 5.0)
            data["slat_transmission"] = win.get("slat_transmission", 5.0)
            data["strategy_high"] = win.get("strategy_high", DEFAULT_STRATEGY_HIGH)
            data["strategy_low"] = win.get("strategy_low", DEFAULT_STRATEGY_LOW)
            data["temp_threshold"] = win.get("temp_threshold", DEFAULT_TEMP_THRESHOLD)
            data["lit_threshold"] = win.get("lit_threshold", DEFAULT_LIT_THRESHOLD)
            data["target_illumination"] = win.get("target_illumination", DEFAULT_TARGET_ILLUMINATION)
            strategy_name = win.get("strategy", "block_all")
            strategy = get_strategy(strategy_name)
            data["strategy"] = strategy_name
            data["desired_position"] = strategy.compute_position(data)
            data["cloud_coverage"] = weather_data["cloud_coverage"]
            data["weather_condition"] = weather_data["weather_condition"]
            data["temperature"] = weather_data["temperature"]
            data["latitude"] = lat
            data["longitude"] = lon
            data["window_idx"] = idx
            results[name] = data

        return results