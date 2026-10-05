<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/sunny/brand/dark_logo.png">
    <img alt="Sunny" src="custom_components/sunny/brand/logo.png" width="520">
  </picture>
</p>

<p align="center"><em>Solar-driven blind and shutter control for Home Assistant.</em></p>

<p align="center">
  <a href="https://github.com/agravelot/sunny/actions/workflows/validate.yml"><img alt="Validate" src="https://github.com/agravelot/sunny/actions/workflows/validate.yml/badge.svg"></a>
  <a href="https://github.com/hacs/integration"><img alt="HACS Custom" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg"></a>
  <img alt="Tests" src="https://img.shields.io/badge/tests-385%20passing-brightgreen.svg">
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-blue.svg">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue.svg">
  <a href="LICENSE.md"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow.svg"></a>
</p>

## Why this project

Blinds are a real trade-off: you want daylight, a view and passive solar gain in winter, yet you also want to keep the summer sun, glare and overheating out. Sunny models the actual **solar geometry** of each window: facade orientation, reveal depth, external obstructions and horizon dip. It then computes how much direct sunlight really lands on the glass and drives each cover with a per-window control strategy.

It is a complete Home Assistant custom integration: a pure-Python calculation core (`solar_math.py`, no Home Assistant imports, 100% unit-tested), twelve pluggable strategies, a coordinator that recomputes every window, and full UI configuration through the Config/Options flow.

## Features

- Computes the direct sunlight percentage on a window from the sun position
- Accounts for facade orientation, wall thickness (reveal), external obstructions (screen wall) and building altitude (horizon dip)
- Integrates weather data (cloud coverage, temperature, condition): a configurable cloud factor dims the estimated direct sunlight
- Creates 4 sensors per window (sun, desired position, active strategy, cloud coverage) + 1 strategy selector
- 12 configurable control strategies per window
- Settings editable at any time via the Home Assistant Config Flow / Options Flow
- Ships brand icons/logos and is HACS compatible
- 385 unit tests, HACS and hassfest validated on every push

## How it works

```mermaid
flowchart LR
    subgraph entry["Config entry"]
        W["Windows<br/>orientation · size · reveal · screen"]
    end
    GEO["hass.config or zone entity<br/>latitude · longitude"]
    WX["Weather entity<br/>cloud · temperature"]
    SM["solar_math.py<br/>pure solar geometry"]
    ST["strategies.py<br/>compute_position()"]
    CO["coordinator.py<br/>DataUpdateCoordinator"]
    ENT["Entities per window<br/>4 sensors · select · 3 numbers<br/>button · auto-control switch"]

    W --> CO
    GEO --> CO
    WX --> CO
    CO --> SM
    SM --> CO
    CO --> ST
    ST --> CO
    CO --> ENT
```

The coordinator resolves the geographic position dynamically: if a `zone_entity` is configured it reads the zone's `latitude`/`longitude` attributes, otherwise it falls back to `hass.config`. Sunlight is recomputed for every window on each refresh (every 5 minutes by default, or on demand through the `sunny.refresh` service).

## Installation

### Via HACS (custom repository)

1. In HACS, add a custom repository: `https://github.com/agravelot/sunny` (type: Integration)
2. Install the Sunny integration
3. Restart Home Assistant

### Manual

Copy the `custom_components/sunny` folder into Home Assistant's `custom_components` directory, then restart.

## Configuration

1. **Settings → Devices & Services → Add Integration → Sunny**
2. Select a weather entity (optional) to enrich sensors with temperature and cloud coverage, and set the cloud influence factor (0-100%)
3. Add one or more windows:

| Parameter | Description | Default |
|-----------|-------------|---------|
| Name | Window name (e.g. Living Room) | required |
| Cover | Associated HA cover entity | required |
| Orientation | Facade azimuth (°, 0=North, 90=East, 180=South, 270=West) | 180 |
| Width | Window width (m) | 1.2 |
| Height | Window height (m) | 1.4 |
| Wall thickness | Reveal depth (m) | 0.25 |
| Altitude | Window height above ground (m) | 10 |
| Ground altitude | Ground / sea level altitude (m) | 208 |
| Relief angle | Minimum solar elevation for the window to count as lit (°) | 3 |
| Tilt threshold | Tilt vs lift threshold (%) | 5 |
| Slat transmission | Light transmission through closed slats (%) | 5 |
| Obstacles | Rectangular boxes in front of the window, given by two corners (x1,y1,z1)-(x2,y2,z2): x left/right, y distance from the facade, z height (m) | none |
| Strategy | Control algorithm (see below) | block_all |
| Threshold high / low | Sunlight thresholds for `threshold` (%) | 50 / 20 |
| Temperature threshold | Temperature trigger for `temperature_guard` (°C) | 28 |
| Light threshold | Sunlight trigger for `temperature_guard` (%) | 20 |
| Target illumination | Target for `target_illumination` (%) | 30 |
| Max illumination | Cap for `max_illumination` (%) | 30 |
| Lux sensors | Indoor illuminance sensors for the `lux_*` strategies | optional |
| Lux area | Area whose illuminance sensors the `lux_*` strategies use | optional |
| Lux high / low | Hysteresis thresholds for the `lux_*` strategies (lx) | 5000 / 3000 |
| Lux step | Position step per update for the `lux_*` strategies (%) | 10 |
| Zone entity | HA zone for geographic position | optional |

4. Sensors are created automatically and update every 5 minutes (configurable).

Parameters can be changed at any time via the **Configure** button on the integration.

### Cloud influence

The optional **cloud influence** factor (weather settings, 0-100%, default 0) dims the estimated direct sunlight by the weather entity's cloud coverage:

**lit_pct_effective = lit_pct × (1 − cloud_fraction × cloud_factor / 100)**

- `0` ignores clouds (default, current behaviour)
- `100` cancels all direct sunlight under a fully overcast sky

Cloud coverage comes from the weather entity's `cloud_coverage` attribute; when it is absent (e.g. met.no), the weather condition is used instead (`sunny`/`clear-night` → 0%, `partlycloudy` → 50%, `cloudy`/`fog`/`rainy`/`snowy`… → 100%). Since `lit_pct` feeds every strategy, the correction applies to all of them (e.g. `max_illumination` opens further when the sky is overcast).

## Sensors

Each window produces the following entities:

| Entity | Type | Description |
|--------|------|-------------|
| `{name} Ensoleillement` | `sensor` | Direct sunlight percentage (0-100%), cloud-adjusted when a cloud influence factor is set |
| `{name} Position désirée` | `sensor` | Recommended blind position (0-100%) |
| `{name} Stratégie` | `sensor` | Currently active strategy name |
| `{name} Couverture nuageuse` | `sensor` | Cloud coverage (%), if weather configured |
| `{name} Choix stratégie` | `select` | Strategy selector (change strategy from the dashboard) |
| `{name} Position min` | `number` | Lower bound for the computed position |
| `{name} Position max` | `number` | Upper bound for the computed position |
| `{name} Ensoleillement max` | `number` | Sunlight cap for the `max_illumination` strategy |
| `{name} Réinitialiser les bornes` | `button` | Resets min/max bounds |
| `{name} Contrôle automatique` | `switch` | Enables automatic cover control |

### Ensoleillement sensor attributes

| Attribute | Description |
|-----------|-------------|
| `solar_altitude` | Solar elevation \( h \) (°) |
| `solar_azimuth` | Solar azimuth \( As \) (°) |
| `gamma` | Azimuth offset (°) |
| `hp` | Profile angle (°) |
| `theta` | Incidence angle (°) |
| `behind` | Sun behind the wall? |
| `d_lat` | Lateral reveal shadow (m) |
| `d_vert` | Lintel reveal shadow (m) |
| `lit_area_m2` | Lit area (m²) |
| `screen_blocks_all` | Screen wall blocking everything? |
| `horizon_dip` | Horizon dip from altitude (°) |

### Position désirée sensor attributes

| Attribute | Description |
|-----------|-------------|
| `cover_entity` | Linked cover entity |
| `tilt_threshold` | Tilt/lift threshold (%) |
| `slat_transmission` | Light transmission through slats (%) |

### Couverture nuageuse sensor attributes

| Attribute | Description |
|-----------|-------------|
| `weather_condition` | Weather state (sunny, cloudy, rainy…) |
| `temperature` | Outside temperature (°C) |

## Control strategies

The strategy determines how `desired_position` is computed. It is chosen per window in the configuration.

| Strategy | Behavior |
|----------|----------|
| **block_all** | Closes just enough to block all direct sunlight. Position = `100 × y_shadow / Hw`. |
| **winter_passive** | Passive solar heating: open (100%) when the sun hits the window, closed (0%) otherwise. |
| **proportional** | `position = 100 - sunlight%`, so more sun means a lower blind. |
| **threshold** | Closed (0%) when sunlight ≥ 50%, open (100%) at ≤ 20%, linear in between. Thresholds are configurable. |
| **temperature_guard** | Applies block_all when the outside temperature ≥ 28 °C and sunlight ≥ 20%, otherwise open (100%). |
| **privacy_night** | Closed (0%) when the sun is below the horizon, open (100%) during the day. |
| **target_illumination** | Finds the blind position that holds direct sunlight at a target (default 30%), using a 5% scan then a binary search. |
| **max_illumination** | Finds the most open position whose direct sunlight stays at or below a cap (default 30%). |
| **always_closed** | Always closed (0%). Useful for thermal insulation or long absences. |
| **always_open** | Always open (100%). Maximum natural light. |
| **lux_target** | Regulates from an indoor illuminance sensor: closes one step (default 10%) above the high threshold (default 5000 lx), opens one step below the low threshold (default 3000 lx), and holds inside the hysteresis band. |
| **lux_target_glare** | The same lux regulation, coordinated across every window sharing the sensor or area: windows without direct sun open first and sunny windows close first, so glare is cut without darkening the whole room. |

The **Position min** and **Position max** numbers clamp the result of any strategy. The two `lux_*` strategies need one or more illuminance sensors (optionally grouped by area) selected in the window configuration.

New strategies can be added in `strategies.py`.

## Automations

Use `desired_position` to control a blind:

```yaml
alias: "Living room blind position"
trigger:
  - platform: state
    entity_id: sensor.salon_position_desiree
action:
  - service: cover.set_cover_position
    target:
      entity_id: cover.living_room_blind
    data:
      position: "{{ state_attr('sensor.salon_position_desiree', 'desired_position') | int }}"
```

Or with a sunlight threshold condition:

```yaml
alias: "Close if high sunlight"
trigger:
  - platform: state
    entity_id: sensor.salon_ensoleillement
condition:
  - condition: numeric_state
    entity_id: sensor.salon_ensoleillement
    above: 40
action:
  - service: cover.set_cover_position
    target:
      entity_id: cover.living_room_blind
    data:
      position: "{{ state_attr('sensor.salon_position_desiree', 'desired_position') | int }}"
```

## Simulator

An interactive simulator is provided in `simulateur_ensoleillement_fenetre.html` (open it directly in a browser):

<p align="center">
  <img alt="Sunlight simulator" src="assets/simulateur.png" width="820">
</p>

- Visualize sunlight on a window in plan and cross-section views
- Test all parameters (orientation, dimensions, screen wall, altitude)
- Connect to Home Assistant to fetch the current sun position
- Place a marker on an OpenStreetMap for geolocation

## Brand assets

The integration icon and logo live in `custom_components/sunny/brand/` (Home Assistant and HACS render them automatically). They are generated from editable SVG sources in `assets/`. Regenerate everything with:

```bash
python3 assets/generate_brand.py    # requires rsvg-convert
```

## Development

```bash
python3 -m pytest tests/ -v         # 385 unit tests
```

Tests do not import Home Assistant: `solar_math.py` and `strategies.py` are pure Python and covered directly.

## References

- `FORMULA.md`: full detail of the solar geometry formulas
- `ui.md`: simulator interface description and known limitations
- `AGENTS.md`: architecture notes and project conventions