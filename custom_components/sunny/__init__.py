"""Intégration Sunny — capteurs d'ensoleillement pour piloter des stores."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SunnyCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "select", "switch", "number", "button"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    from . import services

    services.async_register_services(hass)
    return True


def _migrate_window_ids(entry: ConfigEntry) -> dict | None:
    """Ajoute un champ 'id' stable aux fenêtres qui n'en ont pas encore.

    Retourne les nouvelles options si une migration a eu lieu, None sinon.
    """
    windows = list(entry.options.get("windows", []))
    migrated = False

    for idx, win in enumerate(windows):
        if "id" in win:
            continue
        win = dict(win)
        win["id"] = win.get("cover_entity") or win.get("name", f"fenetre_{idx}")
        windows[idx] = win
        migrated = True

    if not migrated:
        return None

    new_options = dict(entry.options)
    new_options["windows"] = windows
    return new_options


def _migrate_screen_to_obstacles(entry: ConfigEntry) -> dict | None:
    """Convertit screen_distance > 0 en obstacle frontal.

    Retourne les nouvelles options si une migration a eu lieu, None sinon.
    """
    windows = list(entry.options.get("windows", []))
    migrated = False

    for idx, win in enumerate(windows):
        if "obstacles" in win:
            continue
        win = dict(win)
        sd = win.pop("screen_distance", None)
        sh = win.pop("screen_height", None)
        obstacles = list(win.get("obstacles", []))
        if sd is not None and sd > 0:
            obstacles.append({
                "x1": -10000, "y1": sd, "z1": 0,
                "x2": 10000,  "y2": sd + 0.01, "z2": sh or 1.0,
            })
            migrated = True
        win["obstacles"] = obstacles
        windows[idx] = win

    if not migrated:
        return None

    new_options = dict(entry.options)
    new_options["windows"] = windows
    return new_options


_OBSTACLE_KEY_MAP = {"ox1": "x1", "oy1": "y1", "oz1": "z1", "ox2": "x2", "oy2": "y2", "oz2": "z2"}


def _migrate_obstacle_keys(entry: ConfigEntry) -> dict | None:
    """Convertit les clés d'obstacles ox1… → x1… (format canonique du moteur).

    Retourne les nouvelles options si une migration a eu lieu, None sinon.
    """
    windows = list(entry.options.get("windows", []))
    migrated = False

    for idx, win in enumerate(windows):
        obstacles = win.get("obstacles")
        if not obstacles:
            continue
        win = dict(win)
        new_obstacles = []
        for obs in obstacles:
            if "ox1" in obs and "x1" not in obs:
                new_obstacles.append({_OBSTACLE_KEY_MAP.get(k, k): v for k, v in obs.items()})
                migrated = True
            else:
                new_obstacles.append(obs)
        win["obstacles"] = new_obstacles
        windows[idx] = win

    if not migrated:
        return None

    new_options = dict(entry.options)
    new_options["windows"] = windows
    return new_options


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    new_options = _migrate_window_ids(entry)
    if new_options is not None:
        _LOGGER.info("Migration des IDs de fenêtres effectuée")
        hass.config_entries.async_update_entry(entry, options=new_options)

    new_options = _migrate_screen_to_obstacles(entry)
    if new_options is not None:
        _LOGGER.info("Migration screen_distance → obstacles effectuée")
        hass.config_entries.async_update_entry(entry, options=new_options)

    new_options = _migrate_obstacle_keys(entry)
    if new_options is not None:
        _LOGGER.info("Migration des clés d'obstacles effectuée")
        hass.config_entries.async_update_entry(entry, options=new_options)

    coordinator = SunnyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)