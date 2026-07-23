# AGENTS.md

## Language

All code, comments, documentation, and UI are in **French**. Commit messages can be in French or English.

## Project purpose

Home Assistant custom integration to automatically control blinds/shutters based on sunlight, weather, and season.

## Commands

```bash
python3 -m pytest tests/ -v    # 234 unit tests (solar_math + strategies + switch + number + button + services)
```

GitHub CI also validates HACS (`hacs/action`) and hassfest (`home-assistant/actions/hassfest`). No lint, no typecheck, no build.

## Architecture

```
custom_components/sunny/
  __init__.py       # setup entry, window ID migration, add_update_listener
  config_flow.py    # ConfigFlow (creation) + OptionsFlow (edit/delete)
  const.py          # constants (CONF_*, DEFAULT_*)
  coordinator.py    # DataUpdateCoordinator, recomputes sunlight for all windows
  manifest.json     # HA / HACS metadata
  sensor.py         # 4 sensors per window (sun, position, strategy, cloud)
  select.py         # 1 strategy selector per window
  number.py         # 2 number entities per window (min_position, max_position)
  button.py         # 1 button entity per window (reset_bounds)
  solar_math.py     # pure solar geometry calculations (no HA imports)
  strategies.py     # 7 control strategies (compute_position)
  strings.json      # UI translations
```

- Standard HA pattern: CoordinatorEntity → `_handle_coordinator_update()` reads `coordinator.data[window_name]`
- The coordinator is shared via `hass.data[DOMAIN][entry.entry_id]`
- Options flow: `async_create_entry()` saves → `add_update_listener` → `async_reload()` → entities are recreated
- A window without an `id` at startup triggers automatic migration in `__init__.py` (generates `id` from `cover_entity`)

## unique_id format

```
{entry_id}_{window_id}_{window_name}_{suffix}
```

- `entry_id` = HA ConfigEntry UUID
- `window_id` = `cover_entity` (e.g. `cover.living_room_blind`) — stable, never a positional index
- `window_name` = `win["name"]`
- `suffix` = `sun`, `position`, `strategy`, `cloud`, `strategy_select`, `min_position`, `max_position`, `reset_bounds`, `auto_control`

**Never use a positional index in a unique_id.** If a window is removed, indices shift and remaining entities get desynchronized.

## Geographic position

The `latitude`/`longitude` fields do **not** exist in window config. The coordinator resolves them dynamically:
- If `zone_entity` is set → `zone.attributes["latitude"]` / `zone.attributes["longitude"]`
- Otherwise → `hass.config.latitude` / `hass.config.longitude`

## Git conventions

- Single branch `main`
- `pull.rebase = true`
- Commit messages: concise, imperative, lowercase (e.g. `fix duplicate unique_id`)

## Tests

- Tests do **not** import Home Assistant (no `homeassistant.*`). `solar_math.py` and `strategies.py` have no HA dependencies.
- Direct import via `sys.path` hack:
  ```python
  SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
  sys.path.insert(0, str(SRC))
  import solar_math
  ```
- `pytest.ini` enables `asyncio_mode = auto` for potential async tests.

## Simulator

`simulateur_ensoleillement_fenetre.html` — standalone HTML file (~800 lines) to visualize sunlight. Opens directly in a browser. The solar calculation engine is duplicated in JavaScript — any change to `solar_math.py` must be reflected in the simulator.

## Key calculations

See `FORMULA.md` for full formulas. Summary:

- **Solar position**: `h` (elevation) and `As` (azimuth) via declination + hour angle (simplified model)
- **Azimuth offset**: `γ = As − An`. If `|γ| ≥ 90°` → sun behind the wall
- **Profile angle**: `tan hp = tan h / cos γ` — used for vertical shadows
- **Incidence angle**: `cos θ = cos h · cos γ` — Lambert's law
- **Reveal shadows**: `d_lat = e · tan(γ)`, `d_vert = e · tan(hp)`
- **Screen wall**: `y_ombre = max(0, min(Hw, Hm − D · tan(hp)))`
- **Horizon dip**: `dip = arccos(6371 / (6371 + altitude/1000))` — visible if `h > −dip`