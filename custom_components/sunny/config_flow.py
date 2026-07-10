"""Configuration UI pour l'intégration Sunny."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_WEATHER_ENTITY,
    CONF_WINDOWS,
    CONF_WINDOW_NAME,
    CONF_COVER_ENTITY,
    CONF_ORIENTATION,
    CONF_WIDTH,
    CONF_HEIGHT,
    CONF_WALL_THICKNESS,
    CONF_SCREEN_DISTANCE,
    CONF_SCREEN_HEIGHT,
    CONF_TILT_THRESHOLD,
    CONF_SLAT_TRANSMISSION,
    CONF_ALTITUDE,
    CONF_GROUND_ALTITUDE,
    CONF_ZONE_ENTITY,
    CONF_STRATEGY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_REFRESH_INTERVAL,
    CONF_STRATEGY_HIGH,
    CONF_STRATEGY_LOW,
    CONF_TEMP_THRESHOLD,
    CONF_LIT_THRESHOLD,
    CONF_TARGET_ILLUMINATION,
    DEFAULT_NAME,
    DEFAULT_ORIENTATION,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    DEFAULT_WALL_THICKNESS,
    DEFAULT_SCREEN_DISTANCE,
    DEFAULT_SCREEN_HEIGHT,
    DEFAULT_TILT_THRESHOLD,
    DEFAULT_SLAT_TRANSMISSION,
    DEFAULT_ALTITUDE,
    DEFAULT_GROUND_ALTITUDE,
    DEFAULT_STRATEGY,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_STRATEGY_HIGH,
    DEFAULT_STRATEGY_LOW,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_LIT_THRESHOLD,
    DEFAULT_TARGET_ILLUMINATION,
)
from .strategies import STRATEGY_OPTIONS


def _get_cover_friendly_name(hass: HomeAssistant, cover_entity_id: str) -> str:
    state = hass.states.get(cover_entity_id)
    if state and state.attributes.get("friendly_name"):
        return state.attributes["friendly_name"]
    return DEFAULT_NAME


def _is_window_name_duplicate(
    windows: list[dict[str, Any]],
    name: str,
    exclude_idx: int | None = None,
) -> bool:
    for i, win in enumerate(windows):
        if exclude_idx is not None and i == exclude_idx:
            continue
        if win.get(CONF_WINDOW_NAME) == name:
            return True
    return False


def _build_window_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    if defaults is None:
        defaults = {}
    return vol.Schema({
        vol.Required(CONF_WINDOW_NAME, default=defaults.get(CONF_WINDOW_NAME, DEFAULT_NAME)): str,
        vol.Required(CONF_COVER_ENTITY, default=defaults.get(CONF_COVER_ENTITY)):
            EntitySelector(EntitySelectorConfig(domain="cover")),
        vol.Required(CONF_ORIENTATION, default=defaults.get(CONF_ORIENTATION, DEFAULT_ORIENTATION)):
            vol.All(vol.Coerce(float), vol.Range(min=0, max=359)),
        vol.Required(CONF_WIDTH, default=defaults.get(CONF_WIDTH, DEFAULT_WIDTH)):
            vol.All(vol.Coerce(float), vol.Range(min=0.4, max=4.0)),
        vol.Required(CONF_HEIGHT, default=defaults.get(CONF_HEIGHT, DEFAULT_HEIGHT)):
            vol.All(vol.Coerce(float), vol.Range(min=0.4, max=3.0)),
        vol.Required(CONF_WALL_THICKNESS, default=defaults.get(CONF_WALL_THICKNESS, DEFAULT_WALL_THICKNESS)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=0.8)),
        vol.Optional(CONF_SCREEN_DISTANCE, default=defaults.get(CONF_SCREEN_DISTANCE, DEFAULT_SCREEN_DISTANCE)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=20.0)),
        vol.Optional(CONF_SCREEN_HEIGHT, default=defaults.get(CONF_SCREEN_HEIGHT, DEFAULT_SCREEN_HEIGHT)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=15.0)),
        vol.Required(CONF_TILT_THRESHOLD, default=defaults.get(CONF_TILT_THRESHOLD, DEFAULT_TILT_THRESHOLD)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
        vol.Required(CONF_SLAT_TRANSMISSION, default=defaults.get(CONF_SLAT_TRANSMISSION, DEFAULT_SLAT_TRANSMISSION)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
        vol.Required(CONF_ALTITUDE, default=defaults.get(CONF_ALTITUDE, DEFAULT_ALTITUDE)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=500.0)),
        vol.Required(CONF_GROUND_ALTITUDE, default=defaults.get(CONF_GROUND_ALTITUDE, DEFAULT_GROUND_ALTITUDE)):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=3000.0)),
        vol.Required(CONF_STRATEGY, default=defaults.get(CONF_STRATEGY, DEFAULT_STRATEGY)): vol.In(STRATEGY_OPTIONS),
        vol.Optional(CONF_STRATEGY_HIGH, default=defaults.get(CONF_STRATEGY_HIGH, DEFAULT_STRATEGY_HIGH)):
            vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional(CONF_STRATEGY_LOW, default=defaults.get(CONF_STRATEGY_LOW, DEFAULT_STRATEGY_LOW)):
            vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional(CONF_TEMP_THRESHOLD, default=defaults.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD)):
            vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
        vol.Optional(CONF_LIT_THRESHOLD, default=defaults.get(CONF_LIT_THRESHOLD, DEFAULT_LIT_THRESHOLD)):
            vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional(CONF_TARGET_ILLUMINATION, default=defaults.get(CONF_TARGET_ILLUMINATION, DEFAULT_TARGET_ILLUMINATION)):
            vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional(CONF_ZONE_ENTITY, default=defaults.get(CONF_ZONE_ENTITY)):
            EntitySelector(EntitySelectorConfig(domain="zone")),
        vol.Optional(CONF_LATITUDE, default=defaults.get(CONF_LATITUDE)):
            vol.All(vol.Coerce(float), vol.Range(min=-66, max=66)),
        vol.Optional(CONF_LONGITUDE, default=defaults.get(CONF_LONGITUDE)):
            vol.All(vol.Coerce(float), vol.Range(min=-180, max=180)),
    })


def _build_weather_schema() -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="weather")
        ),
    })


class SunnyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour Sunny — sélection météo puis ajout de fenêtres."""

    VERSION = 1

    def __init__(self) -> None:
        self.data: dict[str, Any] = {
            CONF_WINDOWS: [],
            CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL,
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self.data[CONF_WEATHER_ENTITY] = user_input.get(CONF_WEATHER_ENTITY, "")
            return await self.async_step_window()

        return self.async_show_form(
            step_id="user",
            data_schema=_build_weather_schema(),
        )

    async def async_step_window(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = user_input.pop(CONF_LATITUDE, None)
            lon = user_input.pop(CONF_LONGITUDE, None)
            zone_entity = user_input.get(CONF_ZONE_ENTITY)
            if zone_entity and (lat is None or lon is None):
                zone = self.hass.states.get(zone_entity)
                if zone:
                    if lat is None:
                        lat = zone.attributes.get("latitude")
                    if lon is None:
                        lon = zone.attributes.get("longitude")

            name = user_input.get(CONF_WINDOW_NAME, DEFAULT_NAME)
            cover_entity_id = user_input.get(CONF_COVER_ENTITY, "")

            if name == DEFAULT_NAME and cover_entity_id:
                name = _get_cover_friendly_name(self.hass, cover_entity_id)
                user_input[CONF_WINDOW_NAME] = name

            if _is_window_name_duplicate(self.data[CONF_WINDOWS], name):
                errors[CONF_WINDOW_NAME] = "duplicate_name"
            else:
                win: dict[str, Any] = dict(user_input)
                if lat is not None:
                    win[CONF_LATITUDE] = lat
                if lon is not None:
                    win[CONF_LONGITUDE] = lon
                self.data[CONF_WINDOWS].append(win)
                return await self.async_step_finish()

        schema = _build_window_schema(user_input or {})
        if self.data[CONF_WINDOWS]:
            schema = schema.extend({
                vol.Optional("__add_another", default=True): bool,
            })

        return self.async_show_form(
            step_id="window",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "count": str(len(self.data[CONF_WINDOWS]) + 1),
            },
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_window()
            return self.async_create_entry(
                title="Sunny",
                data={},
                options={
                    CONF_WEATHER_ENTITY: self.data.get(CONF_WEATHER_ENTITY, ""),
                    CONF_WINDOWS: self.data[CONF_WINDOWS],
                    CONF_REFRESH_INTERVAL: self.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL),
                },
            )

        return self.async_show_form(
            step_id="finish",
            data_schema=vol.Schema({
                vol.Optional("add_another", default=False): bool,
            }),
            description_placeholders={
                "count": str(len(self.data[CONF_WINDOWS])),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return SunnyOptionsFlow(config_entry)


class SunnyOptionsFlow(OptionsFlow):
    """Options flow — éditer/ajouter/supprimer des fenêtres."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.entry = config_entry
        self.data: dict[str, Any] = dict(config_entry.options)
        if CONF_WINDOWS not in self.data:
            self.data[CONF_WINDOWS] = []
        self._editing: int | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            action = user_input.get("action")
            window_name = user_input.get("window")

            if action == "add":
                return await self.async_step_add_window()
            elif action == "edit" and window_name is not None:
                self._editing = int(window_name)
                return await self.async_step_edit_window()
            elif action == "delete" and window_name is not None:
                idx = int(window_name)
                if 0 <= idx < len(self.data[CONF_WINDOWS]):
                    self.data[CONF_WINDOWS].pop(idx)
                return await self.async_step_init()
            elif action == "weather":
                return await self.async_step_weather()
            elif action == "refresh":
                return await self.async_step_refresh()
            elif action == "done":
                return self.async_create_entry(
                    data=self.entry.data,
                    options=self.data,
                )

        options = [
            {"label": f"{i+1}. {w.get(CONF_WINDOW_NAME, DEFAULT_NAME)}", "value": str(i)}
            for i, w in enumerate(self.data[CONF_WINDOWS])
        ]
        options.append({"label": "+ Ajouter une fenêtre", "value": "add"})

        schema = vol.Schema({
            vol.Required("action"): vol.In(["edit", "delete", "add", "weather", "refresh", "done"]),
            vol.Optional("window"): vol.In({o["value"]: o["label"] for o in options}),
        })

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_edit_window(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            name = user_input.get(CONF_WINDOW_NAME, DEFAULT_NAME)

            if _is_window_name_duplicate(self.data[CONF_WINDOWS], name, exclude_idx=self._editing):
                return self.async_show_form(
                    step_id="edit_window",
                    data_schema=_build_window_schema(user_input),
                    errors={CONF_WINDOW_NAME: "duplicate_name"},
                )

            self.data[CONF_WINDOWS][self._editing] = dict(user_input)
            self._editing = None
            return await self.async_step_init()

        if self._editing is not None and self._editing < len(self.data[CONF_WINDOWS]):
            current = self.data[CONF_WINDOWS][self._editing]
        else:
            current = {}

        return self.async_show_form(
            step_id="edit_window",
            data_schema=_build_window_schema(current),
        )

    async def async_step_add_window(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_WINDOW_NAME, DEFAULT_NAME)
            cover_entity_id = user_input.get(CONF_COVER_ENTITY, "")

            if name == DEFAULT_NAME and cover_entity_id:
                name = _get_cover_friendly_name(self.hass, cover_entity_id)
                user_input[CONF_WINDOW_NAME] = name

            if _is_window_name_duplicate(self.data[CONF_WINDOWS], name):
                errors[CONF_WINDOW_NAME] = "duplicate_name"
            else:
                win = dict(user_input)
                lat = win.pop(CONF_LATITUDE, None)
                lon = win.pop(CONF_LONGITUDE, None)
                zone_entity = win.get(CONF_ZONE_ENTITY)
                if zone_entity and (lat is None or lon is None):
                    zone = self.hass.states.get(zone_entity)
                    if zone:
                        if lat is None:
                            lat = zone.attributes.get("latitude")
                        if lon is None:
                            lon = zone.attributes.get("longitude")
                if lat is not None:
                    win[CONF_LATITUDE] = lat
                if lon is not None:
                    win[CONF_LONGITUDE] = lon
                self.data[CONF_WINDOWS].append(win)
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_window",
            data_schema=_build_window_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_weather(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self.data[CONF_WEATHER_ENTITY] = user_input.get(CONF_WEATHER_ENTITY, "")
            return await self.async_step_init()

        current = self.data.get(CONF_WEATHER_ENTITY) or self.entry.data.get(CONF_WEATHER_ENTITY, "")
        return self.async_show_form(
            step_id="weather",
            data_schema=vol.Schema({
                vol.Optional(CONF_WEATHER_ENTITY, default=current): EntitySelector(
                    EntitySelectorConfig(domain="weather")
                ),
            }),
        )

    async def async_step_refresh(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self.data[CONF_REFRESH_INTERVAL] = user_input[CONF_REFRESH_INTERVAL]
            return await self.async_step_init()

        current = self.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
        return self.async_show_form(
            step_id="refresh",
            data_schema=vol.Schema({
                vol.Required(CONF_REFRESH_INTERVAL, default=current):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }),
        )