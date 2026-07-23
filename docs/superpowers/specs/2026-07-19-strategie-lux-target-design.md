# Stratégie `lux_target` — régulation par capteur lux intérieur

## Objectif

Nouvelle stratégie de pilotage qui maintient un niveau de luminosité intérieure cible en ajustant la position du store par paliers, en se basant sur un ou plusieurs capteurs lux placés dans la pièce.

## Motivation

Les stratégies existantes sont purement géométriques (position du soleil, ombres). Un capteur lux réel dans la pièce permet de prendre en compte la lumière diffuse, les nuages, et l'effet réel des stores — choses que le modèle solaire ne capte pas.

## Architecture

Stratégie **stateless** — pas d'état interne, toute la logique d'orchestration (lecture capteurs, fraîcheur, application) est dans le coordinateur. La stratégie ne fait que le calcul de position cible à partir des données fournies.

```
Coordinateur
  ├── Résolution capteurs (explicites > zone HA)
  ├── Vérification fraîcheur (sensor.last_updated > cover.last_changed)
  ├── Agrégation (moyenne des capteurs frais)
  ├── Appel LuxTargetStrategy.compute_position(data)
  └── Switch applique la position
```

## Configuration par fenêtre

Ajout des champs suivants dans les options de fenêtre :

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `lux_sensors` | `list[str]` | `[]` | Liste d'entity_id de capteurs illuminance |
| `lux_area_id` | `str` | `None` | ID de zone HA pour découverte automatique |
| `lux_high` | `float` | `5000` | Seuil haut (lx) — au-dessus → on ferme |
| `lux_low` | `float` | `3000` | Seuil bas (lx) — en-dessous → on ouvre |
| `lux_step` | `int` | `10` | Pas d'ajustement (%) |

### Résolution des capteurs

1. Si `lux_sensors` est non-vide → on utilise cette liste explicitement
2. Sinon si `lux_area_id` est défini → découverte via `entity_registry` : toutes les entités `sensor` avec `device_class == "illuminance"` dans cette zone
3. Si aucun capteur trouvé → **WARNING**, position inchangée

## Logique de régulation

```
Pour chaque cycle du coordinateur (fenêtre avec strategy == "lux_target") :

1. Résoudre la liste des capteurs
2. Lire last_updated de chaque capteur
3. Lire last_changed du cover
4. Si TOUS les capteurs sont plus vieux que le dernier mouvement du cover :
   → LOG "capteurs stale", position inchangée
5. Si au moins UN capteur est plus récent que le mouvement :
   → Agréger les valeurs des capteurs frais (moyenne)
   → Appeler LuxTargetStrategy.compute_position()
6. Si lux > lux_high  → position = max(0, current - lux_step)
   Si lux < lux_low   → position = min(100, current + lux_step)
   Sinon              → position inchangée (zone morte)
```

### Hystérésis

La zone morte entre `lux_low` et `lux_high` évite les oscillations. Une fois que la position entre dans cette zone, elle y reste tant que le lux ne dépasse pas les seuils.

## Logging

| Niveau | Événement |
|--------|-----------|
| `DEBUG` | Capteurs découverts/résolus, valeurs lues par capteur, agrégation |
| `INFO` | Changement de position décidé (ancienne → nouvelle, lux mesuré) |
| `WARNING` | Aucun capteur trouvé, tous les capteurs sont stale, valeur aberrante |

## Implémentation

### Nouveaux fichiers / fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `const.py` | Nouvelles constantes `CONF_LUX_*`, `DEFAULT_*` |
| `strategies.py` | Nouvelle classe `LuxTargetStrategy` |
| `coordinator.py` | Résolution capteurs, vérification fraîcheur, agrégation, appel stratégie |
| `config_flow.py` | Bloc conditionnel lux dans l'OptionsFlow (si stratégie = "lux_target") |
| `strings.json` | Labels pour les nouveaux champs |
| `tests/test_strategies.py` | ~10 tests unitaires |

### Stratégie (pseudocode)

```python
class LuxTargetStrategy(BaseStrategy):
    name = "lux_target"
    label = "Cible lux intérieur (capteur)"

    def compute_position(self, data: dict) -> int:
        lux = data.get("lux_value")
        cur = data.get("current_position", 100)
        high = data.get("lux_high", 5000)
        low = data.get("lux_low", 3000)
        step = data.get("lux_step", 10)

        if lux is None:
            return cur

        if lux > high:
            return max(0, cur - step)
        if lux < low:
            return min(100, cur + step)
        return cur
```

## Tests

Cas unitaires pour `LuxTargetStrategy.compute_position` :

1. `lux > high` → fermeture d'un pas (`cur - step`)
2. `lux < low` → ouverture d'un pas (`cur + step`)
3. `low <= lux <= high` → position inchangée
4. `lux = None` → position inchangée
5. Position déjà à 0, lux > high → reste à 0 (clamping)
6. Position déjà à 100, lux < low → reste à 100 (clamping)
7. lux == high (limite supérieure de la zone morte) → inchangé
8. lux == low (limite inférieure de la zone morte) → inchangé
9. step configurable (step=5, step=20)
10. lux très au-dessus du seuil → un seul pas par cycle (pas d'accumulation)

## Non-objectifs (volontairement exclus)

- Pas d'utilisation du modèle solaire (pilotage pur capteur)
- Pas de PID ni de pas proportionnel
- Pas de position de repli sur timeout capteur (on garde la position)
- Pas de réactivation automatique après stale (le prochain cycle frais appliquera le pas)