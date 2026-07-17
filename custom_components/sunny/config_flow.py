"""Configuration UI pour l'intégration Sunny."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_POSITION_THRESHOLD,
    DEFAULT_POSITION_THRESHOLD,
    CONF_WEATHER_ENTITY,
    CONF_WINDOWS,
    CONF_WINDOW_NAME,
    CONF_WINDOW_ID,
    CONF_COVER_ENTITY,
    CONF_ORIENTATION,
    CONF_WIDTH,
    CONF_HEIGHT,
    CONF_WALL_THICKNESS,
    CONF_OBSTACLES,
    CONF_OBSTACLE_X1,
    CONF_OBSTACLE_Y1,
    CONF_OBSTACLE_Z1,
    CONF_OBSTACLE_X2,
    CONF_OBSTACLE_Y2,
    CONF_OBSTACLE_Z2,
    CONF_TILT_THRESHOLD,
    CONF_SLAT_TRANSMISSION,
    CONF_ALTITUDE,
    CONF_GROUND_ALTITUDE,
    CONF_ZONE_ENTITY,
    CONF_STRATEGY,
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
    DEFAULT_OBSTACLE_X1,
    DEFAULT_OBSTACLE_Y1,
    DEFAULT_OBSTACLE_Z1,
    DEFAULT_OBSTACLE_X2,
    DEFAULT_OBSTACLE_Y2,
    DEFAULT_OBSTACLE_Z2,
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
    })


def _build_weather_schema() -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="weather")
        ),
    })


def _build_obstacle_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    if defaults is None:
        defaults = {}
    return vol.Schema({
        vol.Required(CONF_OBSTACLE_X1, default=defaults.get(CONF_OBSTACLE_X1, DEFAULT_OBSTACLE_X1)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Y1, default=defaults.get(CONF_OBSTACLE_Y1, DEFAULT_OBSTACLE_Y1)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Z1, default=defaults.get(CONF_OBSTACLE_Z1, DEFAULT_OBSTACLE_Z1)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_X2, default=defaults.get(CONF_OBSTACLE_X2, DEFAULT_OBSTACLE_X2)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Y2, default=defaults.get(CONF_OBSTACLE_Y2, DEFAULT_OBSTACLE_Y2)):
            vol.All(vol.Coerce(float)),
        vol.Required(CONF_OBSTACLE_Z2, default=defaults.get(CONF_OBSTACLE_Z2, DEFAULT_OBSTACLE_Z2)):
            vol.All(vol.Coerce(float)),
    })


def _cleanup_window_entities(
    hass: HomeAssistant,
    entry_id: str,
    window_name: str,
    window_id: str,
) -> None:
    """Supprime les entités et le device fallback associés à une fenêtre."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    for domain, suffix in [
        ("sensor", "sun"),
        ("sensor", "position"),
        ("sensor", "strategy"),
        ("sensor", "cloud"),
        ("select", "strategy_select"),
        ("switch", "auto_control"),
    ]:
        unique_id = f"{entry_id}_{window_id}_{window_name}_{suffix}"
        entity_id = ent_reg.async_get_entity_id(domain, DOMAIN, unique_id)
        if entity_id:
            ent_reg.async_remove(entity_id)

    device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{entry_id}_{window_name}")})
    if device and device.manufacturer == "Sunny":
        dev_reg.async_remove_device(device.id)


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
            name = user_input.get(CONF_WINDOW_NAME, DEFAULT_NAME)
            cover_entity_id = user_input.get(CONF_COVER_ENTITY, "")

            if name == DEFAULT_NAME and cover_entity_id:
                name = _get_cover_friendly_name(self.hass, cover_entity_id)
                user_input[CONF_WINDOW_NAME] = name

            if _is_window_name_duplicate(self.data[CONF_WINDOWS], name):
                errors[CONF_WINDOW_NAME] = "duplicate_name"
            else:
                win: dict[str, Any] = dict(user_input)
                win[CONF_WINDOW_ID] = win.get(CONF_COVER_ENTITY, "")
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
        self._obstacle_editing: int = -1

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
                    win = self.data[CONF_WINDOWS][idx]
                    _cleanup_window_entities(
                        self.hass,
                        self.entry.entry_id,
                        win.get(CONF_WINDOW_NAME, ""),
                        win.get("id", ""),
                    )
                    self.data[CONF_WINDOWS].pop(idx)
                return await self.async_step_init()
            elif action == "weather":
                return await self.async_step_weather()
            elif action == "refresh":
                return await self.async_step_refresh()
            elif action == "position_threshold":
                return await self.async_step_position_threshold()
            elif action == "obstacles" and window_name is not None:
                self._editing = int(window_name)
                return await self.async_step_obstacles()
            elif action == "done":
                return self.async_create_entry(data=self.data)

        options = [
            {"label": f"{i+1}. {w.get(CONF_WINDOW_NAME, DEFAULT_NAME)}", "value": str(i)}
            for i, w in enumerate(self.data[CONF_WINDOWS])
        ]
        options.append({"label": "+ Ajouter une fenêtre", "value": "add"})

        schema = vol.Schema({
            vol.Required("action"): vol.In(["edit", "delete", "add", "weather", "refresh", "position_threshold", "obstacles", "done"]),
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
                win[CONF_WINDOW_ID] = win.get(CONF_COVER_ENTITY, "")
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

    async def async_step_position_threshold(
        self, user_input: dict[str, Any] | None = None
    ):
        if user_input is not None:
            self.data[CONF_POSITION_THRESHOLD] = user_input[CONF_POSITION_THRESHOLD]
            return await self.async_step_init()

        current = self.data.get(CONF_POSITION_THRESHOLD, DEFAULT_POSITION_THRESHOLD)
        return self.async_show_form(
            step_id="position_threshold",
            data_schema=vol.Schema({
                vol.Required(CONF_POSITION_THRESHOLD, default=current):
                    NumberSelector(
                        NumberSelectorConfig(min=0, max=20, step=1, mode=NumberSelectorMode.BOX)
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

    async def async_step_obstacles(self, user_input: dict[str, Any] | None = None):
        """Liste des obstacles d'une fenêtre avec actions ajouter/modifier/supprimer."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_obstacle()
            elif action == "back":
                return await self.async_step_init()
            elif action is not None:
                # "edit_N" ou "delete_N"
                parts = action.split("_", 1)
                if len(parts) == 2:
                    idx = int(parts[1])
                    windows = self.data.get(CONF_WINDOWS, [])
                    if self._editing is not None and self._editing < len(windows):
                        win = windows[self._editing]
                        obstacles = list(win.get(CONF_OBSTACLES, []))
                        if parts[0] == "edit" and 0 <= idx < len(obstacles):
                            self._obstacle_editing = idx
                            return await self.async_step_edit_obstacle()
                        elif parts[0] == "delete" and 0 <= idx < len(obstacles):
                            obstacles.pop(idx)
                            win = dict(win)
                            win[CONF_OBSTACLES] = obstacles
                            windows[self._editing] = win
                            self.data[CONF_WINDOWS] = windows
                return await self.async_step_obstacles()

        windows = self.data.get(CONF_WINDOWS, [])
        obstacles = []
        if self._editing is not None and self._editing < len(windows):
            obstacles = windows[self._editing].get(CONF_OBSTACLES, [])

        options = []
        for i, obs in enumerate(obstacles):
            label = f"Obstacle {i+1} : ({obs.get(CONF_OBSTACLE_X1,0)},{obs.get(CONF_OBSTACLE_Y1,0)},{obs.get(CONF_OBSTACLE_Z1,0)})→({obs.get(CONF_OBSTACLE_X2,0)},{obs.get(CONF_OBSTACLE_Y2,0)},{obs.get(CONF_OBSTACLE_Z2,0)})"
            options.extend([
                {"label": f"✏️ {label}", "value": f"edit_{i}"},
                {"label": f"🗑️ Supprimer", "value": f"delete_{i}"},
            ])

        schema = vol.Schema({
            vol.Required("action"): vol.In(
                {o["value"]: o["label"] for o in options} | {"add": "+ Ajouter un obstacle", "back": "← Retour"}
            ),
        })

        return self.async_show_form(step_id="obstacles", data_schema=schema)

    async def async_step_add_obstacle(self, user_input: dict[str, Any] | None = None):
        """Formulaire d'ajout d'un obstacle."""
        if user_input is not None:
            windows = self.data.get(CONF_WINDOWS, [])
            if self._editing is not None and self._editing < len(windows):
                win = dict(windows[self._editing])
                obstacles = list(win.get(CONF_OBSTACLES, []))
                obstacles.append({
                    CONF_OBSTACLE_X1: user_input[CONF_OBSTACLE_X1],
                    CONF_OBSTACLE_Y1: user_input[CONF_OBSTACLE_Y1],
                    CONF_OBSTACLE_Z1: user_input[CONF_OBSTACLE_Z1],
                    CONF_OBSTACLE_X2: user_input[CONF_OBSTACLE_X2],
                    CONF_OBSTACLE_Y2: user_input[CONF_OBSTACLE_Y2],
                    CONF_OBSTACLE_Z2: user_input[CONF_OBSTACLE_Z2],
                })
                win[CONF_OBSTACLES] = obstacles
                windows[self._editing] = win
                self.data[CONF_WINDOWS] = windows
            return await self.async_step_obstacles()

        return self.async_show_form(
            step_id="add_obstacle",
            data_schema=_build_obstacle_schema(),
        )

    async def async_step_edit_obstacle(self, user_input: dict[str, Any] | None = None):
        """Formulaire d'édition d'un obstacle existant."""
        if user_input is not None:
            windows = self.data.get(CONF_WINDOWS, [])
            if self._editing is not None and self._editing < len(windows):
                win = dict(windows[self._editing])
                obstacles = list(win.get(CONF_OBSTACLES, []))
                idx = getattr(self, "_obstacle_editing", -1)
                if 0 <= idx < len(obstacles):
                    obstacles[idx] = {
                        CONF_OBSTACLE_X1: user_input[CONF_OBSTACLE_X1],
                        CONF_OBSTACLE_Y1: user_input[CONF_OBSTACLE_Y1],
                        CONF_OBSTACLE_Z1: user_input[CONF_OBSTACLE_Z1],
                        CONF_OBSTACLE_X2: user_input[CONF_OBSTACLE_X2],
                        CONF_OBSTACLE_Y2: user_input[CONF_OBSTACLE_Y2],
                        CONF_OBSTACLE_Z2: user_input[CONF_OBSTACLE_Z2],
                    }
                    win[CONF_OBSTACLES] = obstacles
                    windows[self._editing] = win
                    self.data[CONF_WINDOWS] = windows
            self._obstacle_editing = -1
            return await self.async_step_obstacles()

        windows = self.data.get(CONF_WINDOWS, [])
        current = {}
        if self._editing is not None and self._editing < len(windows):
            obstacles = windows[self._editing].get(CONF_OBSTACLES, [])
            idx = getattr(self, "_obstacle_editing", -1)
            if 0 <= idx < len(obstacles):
                current = obstacles[idx]

        return self.async_show_form(
            step_id="edit_obstacle",
            data_schema=_build_obstacle_schema(current),
        )