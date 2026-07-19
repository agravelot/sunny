# Seuil de tolérance de position

**Date** : 2026-07-15
**Statut** : spec

## Objectif

Éviter d'envoyer des commandes `set_cover_position` au store quand la position désirée a peu changé (ex. 1%). Cela réduit les micro-ajustements inutiles et le bruit sur le réseau Zigbee/ZWave.

Un seuil global (configurable, 3% par défaut) définit le changement minimum nécessaire avant d'ordonner un mouvement. Deux règles supplémentaires complètent le comportement.

## Règles

1. **Toujours appliquer 0 ou 100** — les positions extrêmes (fermé/ouvert) sont prioritaires, quel que soit le seuil.
2. **Ne jamais envoyer si `new == current`** — si le cover est déjà à la position désirée, pas de commande.
3. **Appliquer uniquement si `abs(new - current) >= threshold`** — sinon, ignorer (hors cas 1 et 2).

La position `current` est lue depuis l'état réel du cover (`hass.states.get(cover_entity)`), pas depuis un état interne. Cela garantit la robustesse après un redémarrage HA ou un déplacement manuel.

## Fichiers modifiés

### `const.py`
- `CONF_POSITION_THRESHOLD = "position_threshold"`
- `DEFAULT_POSITION_THRESHOLD = 3`

### `switch.py` — logique métier

Ajout de la méthode `_should_apply(self, new, threshold, cover_entity) -> bool` :

```python
def _should_apply(self, new: int, threshold: int, cover_entity: str) -> bool:
    state = self.hass.states.get(cover_entity)
    if state is None or state.state in ("unavailable", "unknown"):
        return True
    try:
        current = int(float(state.state))
    except (ValueError, TypeError):
        return True
    if new == current:
        return False
    if new in (0, 100):
        return True
    return abs(new - current) >= threshold
```

Modification de `_handle_coordinator_update` : lecture du seuil depuis `self.coordinator.entry.options`, appel à `_should_apply` avant d'envoyer la commande.

`async_turn_on` : même logique `_should_apply` (pas de bypass, lire l'état réel).

### `config_flow.py`

Dans `SunnyOptionsFlow` :
- Nouvelle action `"position_threshold"` dans `async_step_init`
- Nouvelle étape `async_step_position_threshold` : `NumberSelector` min=0, max=20, step=1, mode `BOX`, valeur par défaut = valeur actuelle dans `entry.options` ou 3

### `strings.json`

Ajout de l'action `"position_threshold": "Changer le seuil de position"` et de l'étape :
```json
"position_threshold": {
    "title": "Seuil de tolérance de position",
    "data": {
        "position_threshold": "Seuil minimum de changement (%)"
    }
}
```

### `tests/test_switch.py` (nouveau)

Tests unitaires de `_should_apply` avec mock de `hass.states.get`.

| Cas | current | new | threshold | résultat | règle |
|-----|---------|-----|-----------|----------|-------|
| État `None` | `None` | 50 | 3 | `True` | fallback |
| `unavailable` | `"unavailable"` | 50 | 3 | `True` | fallback |
| `unknown` | `"unknown"` | 50 | 3 | `True` | fallback |
| Position invalide | `"closed"` | 50 | 3 | `True` | fallback |
| Même position | 50 | 50 | 3 | `False` | règle 2 |
| Vers 0 | 50 | 0 | 3 | `True` | règle 1 |
| Vers 100 | 50 | 100 | 3 | `True` | règle 1 |
| Depuis 0 vers 0 | 0 | 0 | 3 | `False` | règle 2 |
| Changement >= seuil | 50 | 54 | 3 | `True` | règle 3 |
| Changement < seuil | 50 | 52 | 3 | `False` | règle 3 |
| Seuil désactivé (0) | 50 | 51 | 0 | `True` | règle 3 |

## Non-impacté

- `coordinator.py` — inchangé, continue de calculer `desired_position` normalement
- `sensor.py` — le capteur `position` continue d'afficher la position désirée calculée, même si elle n'est pas appliquée
- `strategies.py`, `solar_math.py` — inchangés
- `select.py` — inchangé
- `__init__.py` — inchangé
- `simulateur_ensoleillement_fenetre.html` — non concerné