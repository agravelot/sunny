"""Coordinateur de données pour l'intégration Sunny."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL_MINUTES
from .solar_math import compute_window

_LOGGER = logging.getLogger(__name__)


class SunnyCoordinator(DataUpdateCoordinator):
    """Coordinateur qui recalcule l'ensoleillement périodiquement."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry

    async def _async_update_data(self) -> dict:
        sun = self.hass.states.get("sun.sun")
        if sun is None:
            _LOGGER.warning("Entité sun.sun introuvable")
            return {}

        h = sun.attributes.get("elevation")
        As = sun.attributes.get("azimuth")
        if h is None or As is None:
            _LOGGER.warning("sun.sun sans elevation ou azimuth")
            return {}

        weather_data = {"cloud_coverage": None, "weather_condition": None, "temperature": None}
        weather_entity = self.entry.data.get("weather_entity") or self.entry.options.get("weather_entity")
        if weather_entity:
            weather = self.hass.states.get(weather_entity)
            if weather:
                weather_data["cloud_coverage"] = weather.attributes.get("cloud_coverage")
                weather_data["weather_condition"] = weather.state
                weather_data["temperature"] = weather.attributes.get("temperature")

        results = {}
        windows = self.entry.options.get("windows", [])
        for win in windows:
            name = win.get("name", "Fenêtre")
            lat = win.get("latitude", self.hass.config.latitude)
            lon = win.get("longitude", self.hass.config.longitude)
            orientation = win.get("orientation", 180)
            width = win.get("width", 1.2)
            height = win.get("height", 1.4)
            wall = win.get("wall_thickness", 0.25)
            sd = win.get("screen_distance", 0.0)
            sh = win.get("screen_height", 1.0)
            alt = win.get("altitude", 10)

            data = compute_window(
                h=h, As=As, An=orientation,
                W=width, Hw=height, e=wall,
                D=sd, Hm=sh, altitude=alt,
            )
            data["cover_entity"] = win.get("cover_entity")
            data["cloud_coverage"] = weather_data["cloud_coverage"]
            data["weather_condition"] = weather_data["weather_condition"]
            data["temperature"] = weather_data["temperature"]
            data["latitude"] = lat
            data["longitude"] = lon
            results[name] = data

        return results