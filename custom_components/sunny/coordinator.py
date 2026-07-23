"""Coordinateur de données pour l'intégration Sunny."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_RELIEF_ANGLE,
    DEFAULT_STRATEGY_HIGH,
    DEFAULT_STRATEGY_LOW,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_LIT_THRESHOLD,
    DEFAULT_TARGET_ILLUMINATION,
    CONF_LUX_SENSORS,
    CONF_LUX_AREA_ID,
    CONF_LUX_HIGH,
    CONF_LUX_LOW,
    CONF_LUX_STEP,
    DEFAULT_LUX_HIGH,
    DEFAULT_LUX_LOW,
    DEFAULT_LUX_STEP,
    CONF_MIN_POSITION,
    CONF_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DEFAULT_MAX_POSITION,
    CONF_STAGGER_DELAY,
    DEFAULT_STAGGER_DELAY,
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

    @property
    def stagger_delay(self) -> int:
        return self.entry.options.get(CONF_STAGGER_DELAY, DEFAULT_STAGGER_DELAY)

    def _resolve_lux_sensors(self, win: dict) -> list[str]:
        """Résout la liste des capteurs lux pour une fenêtre.

        Priorité : lux_sensors (explicite) > lux_area_id (découverte zone HA).
        """
        explicit = win.get("lux_sensors", [])
        if isinstance(explicit, str):
            explicit = [explicit]
        if explicit:
            return [e for e in explicit if isinstance(e, str) and e]

        area_id = win.get("lux_area_id")
        if not area_id:
            return []

        ent_reg = er.async_get(self.hass)
        sensors = []
        for entity in ent_reg.entities.values():
            if (
                entity.domain == "sensor"
                and entity.area_id == area_id
                and entity.device_class == "illuminance"
                and not entity.disabled
            ):
                sensors.append(entity.entity_id)
        return sensors

    def _compute_lux_target_position(self, win: dict, strategy) -> int:
        """Calcule la position pour une fenêtre en stratégie lux_target.

        Retourne la position inchangée si aucun capteur frais.
        """
        cover_entity = win.get("cover_entity", "")
        cover_state = self.hass.states.get(cover_entity)
        current_position = 100
        cover_last_changed = None
        if cover_state is not None:
            pos = cover_state.attributes.get("current_position")
            if pos is not None:
                try:
                    current_position = int(float(pos))
                except (ValueError, TypeError):
                    pass
            cover_last_changed = cover_state.last_changed

        sensor_ids = self._resolve_lux_sensors(win)
        if not sensor_ids:
            _LOGGER.warning(
                "Aucun capteur lux trouvé pour la fenêtre '%s' (lux_sensors=%s, lux_area_id=%s)",
                win.get("name", "Inconnue"),
                win.get("lux_sensors", []),
                win.get("lux_area_id"),
            )
            return current_position

        fresh_values = []
        stale_count = 0
        for sid in sensor_ids:
            sensor_state = self.hass.states.get(sid)
            if sensor_state is None:
                _LOGGER.debug("Capteur lux '%s' introuvable", sid)
                continue
            if cover_last_changed is not None and sensor_state.last_updated <= cover_last_changed:
                stale_count += 1
                _LOGGER.debug(
                    "Capteur lux '%s' stale (last_updated=%s <= cover.last_changed=%s)",
                    sid, sensor_state.last_updated, cover_last_changed,
                )
                continue
            try:
                val = float(sensor_state.state)
                fresh_values.append(val)
                _LOGGER.debug(
                    "Capteur lux '%s' frais : %s lx (last_updated=%s)",
                    sid, val, sensor_state.last_updated,
                )
            except (ValueError, TypeError):
                _LOGGER.debug("Capteur lux '%s' valeur non numérique: %s", sid, sensor_state.state)

        if not fresh_values:
            _LOGGER.info(
                "Aucun capteur frais pour la fenêtre '%s' (%d stale sur %d), position inchangée à %d",
                win.get("name", "Inconnue"), stale_count, len(sensor_ids), current_position,
            )
            return current_position

        lux_value = sum(fresh_values) / len(fresh_values)
        _LOGGER.debug(
            "Lux agrégé pour '%s': %.0f lx (moyenne de %d capteurs)",
            win.get("name", "Inconnue"), lux_value, len(fresh_values),
        )

        data = {
            "lux_value": lux_value,
            "current_position": current_position,
            "lux_high": win.get("lux_high", DEFAULT_LUX_HIGH),
            "lux_low": win.get("lux_low", DEFAULT_LUX_LOW),
            "lux_step": win.get("lux_step", DEFAULT_LUX_STEP),
        }
        new_position = strategy.compute_position(data)
        if new_position != current_position:
            _LOGGER.info(
                "Lux target '%s': lux=%.0f lx, position %d → %d",
                win.get("name", "Inconnue"), lux_value, current_position, new_position,
            )
        return new_position

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
            relief_angle = win.get("relief_angle", DEFAULT_RELIEF_ANGLE)

            try:
                data = compute_window(
                    h=h, As=As, An=orientation,
                    W=width, Hw=height, e=wall,
                    obstacles=obstacles, altitude=alt,
                    ground_altitude=ground_alt,
                    relief_angle=relief_angle,
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
            if strategy_name == "lux_target":
                data["desired_position"] = self._compute_lux_target_position(win, strategy)
            else:
                data["desired_position"] = strategy.compute_position(data)
            min_pos = int(win.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION))
            max_pos = int(win.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION))
            data["desired_position"] = max(min_pos, min(max_pos, data["desired_position"]))
            data["cloud_coverage"] = weather_data["cloud_coverage"]
            data["weather_condition"] = weather_data["weather_condition"]
            data["temperature"] = weather_data["temperature"]
            data["latitude"] = lat
            data["longitude"] = lon
            data["window_idx"] = idx
            results[name] = data

        return results