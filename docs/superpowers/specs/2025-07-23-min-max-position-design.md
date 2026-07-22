# Bornes min/max de position désirée par store

## Contexte

L'utilisateur souhaite pouvoir borner la position désirée calculée par la stratégie de pilotage entre un minimum et un maximum, réglables au runtime et persistés.

## Architecture

### Nouvelles constantes (`const.py`)

- `CONF_MIN_POSITION = "min_position"` — clé dans la config de la fenêtre
- `CONF_MAX_POSITION = "max_position"` — clé dans la config de la fenêtre
- `DEFAULT_MIN_POSITION = 0`
- `DEFAULT_MAX_POSITION = 100`

### Clamping dans le coordinateur (`coordinator.py`)

Dans `_async_update_data`, après le calcul de `desired_position` par la stratégie :

```python
min_pos = int(win.get("min_position", 0))
max_pos = int(win.get("max_position", 100))
data["desired_position"] = max(min_pos, min(max_pos, data["desired_position"]))
```

Si les bornes ne sont pas encore définies dans la config, le comportement est inchangé (0-100).

### Nouvelle plateforme `number` (`number.py`)

Deux entités `number` par store :

| Entité | Valeur min | Valeur max | Défaut | Pas |
|--------|-----------|-----------|--------|-----|
| `{store} Position min` | 0 | 100 | 0 | 1 |
| `{store} Position max` | 0 | 100 | 100 | 1 |

- Utilisent `NumberSelectorMode.BOX`
- Utilisent `RestoreEntity` pour restaurer l'état après recréation
- `native_value` lit la valeur depuis `entry.options.windows[N]`
- `async_set_value()` :
  1. Valide que min < max et max > min par rapport à l'autre borne
  2. Écrit dans `entry.options.windows[N]`
  3. Persiste via `hass.config_entries.async_update_entry` (même pattern que `select.py`)
  4. Rafraîchit le coordinator
- `unique_id` : `{entry_id}_{window_id}_{window_name}_min_position` / `_max_position`

### Nouvelle plateforme `button` (`button.py`)

Une entité `button` par store : `{store} Réinitialiser bornes`

- `async_press()` : appelle `number.set_value` sur les deux entités number avec 0 et 100
- `unique_id` : `{entry_id}_{window_id}_{window_name}_reset_bounds`
- Pas de `RestoreEntity` (stateless)

### Enregistrement des plateformes (`__init__.py`)

```python
PLATFORMS = ["sensor", "select", "switch", "number", "button"]
```

Aucun changement nécessaire dans `manifest.json` (les plateformes native HA n'ont pas de dépendance explicite).

### Nettoyage (`config_flow.py`)

Ajouter `number` et `button` dans `_cleanup_window_entities` pour supprimer les entités orphelines à la suppression d'une fenêtre.

### Traductions (`strings.json`)

Aucune modification nécessaire — les noms d'entités sont définis dans le code.

## Tests

### `tests/test_number.py`

- `test_min_position_creation` — vérifie name, unique_id, min/max/step
- `test_max_position_creation` — idem pour max
- `test_default_values_no_config` — si pas dans options, native_value = 0 pour min, 100 pour max
- `test_values_from_options` — native_value lit depuis entry.options
- `test_set_value_min` — écriture et persistance
- `test_set_value_max` — idem
- `test_min_cannot_exceed_max` — async_set_value refuse si min >= max
- `test_max_cannot_be_below_min` — async_set_value refuse si max <= min

### `tests/test_button.py`

- `test_press_resets_bounds` — appelle number.set_value(0) et number.set_value(100)
- `test_unique_id`
- `test_entity_name`

### Tests existants

- `test_switch.py` : aucun changement (le clamping est transparent côté switch)
- `test_strategies.py` : aucun changement
- `test_coordinator.py` : (pas de test coordinator existant, pas de nouveau fichier créé)

## Fichiers modifiés

| Fichier | Changement |
|---------|-----------|
| `custom_components/sunny/const.py` | +3 constantes |
| `custom_components/sunny/coordinator.py` | +4 lignes de clamping |
| `custom_components/sunny/__init__.py` | +2 plateformes |
| `custom_components/sunny/config_flow.py` | +2 domaines dans cleanup |


## Fichiers créés

| Fichier | Description |
|---------|-------------|
| `custom_components/sunny/number.py` | Plateforme number (2 entités / store) |
| `custom_components/sunny/button.py` | Plateforme button (1 entité / store) |
| `tests/test_number.py` | Tests unitaires number |
| `tests/test_button.py` | Tests unitaires button |