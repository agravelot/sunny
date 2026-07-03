# Sunny

Intégration Home Assistant pour le pilotage solaire des stores et volets.

## Fonctionnalités

- Calcule le pourcentage d'ensoleillement direct sur une fenêtre en fonction de la position du soleil
- Prend en compte l'orientation de la façade, l'épaisseur du mur (embrasure), les obstructions extérieures (mur écran) et l'altitude du logement (horizon dip)
- Intègre les données météo (couverture nuageuse, température, condition) pour enrichir les capteurs
- Crée un capteur par fenêtre avec une position de store recommandée (`desired_position`)
- 7 stratégies de pilotage configurables par fenêtre
- Paramètres éditables via l'interface de configuration HA (Config Flow / Options Flow)
- Compatible HACS

## Installation

### Via HACS (custom repository)

1. Dans HACS, ajouter un dépôt personnalisé : `https://github.com/agravelot/sunny` (type : Integration)
2. Installer l'intégration Sunny
3. Redémarrer Home Assistant

### Manuellement

Copier le dossier `custom_components/sunny` dans le répertoire `custom_components` de Home Assistant, puis redémarrer.

## Configuration

1. **Paramètres → Appareils et services → Ajouter une intégration → Sunny**
2. Sélectionner une entité météo (optionnelle) — enrichit les capteurs avec la température et la couverture nuageuse
3. Ajouter une ou plusieurs fenêtres :

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| Nom | Nom de la fenêtre (ex: Salon) | — |
| Store | Entité cover HA associée | — |
| Orientation | Azimut de la façade (°, 0=Nord, 90=Est, 180=Sud, 270=Ouest) | 180 |
| Largeur | Largeur de la fenêtre (m) | 1.2 |
| Hauteur | Hauteur de la fenêtre (m) | 1.4 |
| Épaisseur du mur | Profondeur de l'embrasure (m) | 0.25 |
| Distance mur écran | Obstruction extérieure (m, 0 = désactivé) | 0 |
| Hauteur mur écran | Hauteur de l'obstruction (m) | 1.0 |
| Altitude | Hauteur de la fenêtre au-dessus du sol (m) | 10 |
| Stratégie | Algorithme de pilotage | block_all |
| Entité zone | Zone HA pour la position géographique | optionnel |
| Latitude / Longitude | Coordonnées manuelles (fallback) | depuis HA |

4. Les capteurs `sensor.sunny_*` sont créés automatiquement et se mettent à jour toutes les 5 minutes.

Les paramètres sont modifiables à tout moment via le bouton **Configurer** de l'intégration.

## Capteur

Chaque fenêtre produit un capteur `sensor.sunny_{nom}` :

| Attribut | Description |
|----------|-------------|
| **state** | Pourcentage d'ensoleillement direct (0–100 %) |
| `solar_altitude` | Hauteur solaire \( h \) (°) |
| `solar_azimuth` | Azimut solaire \( As \) (°) |
| `gamma` | Écart azimutal (°) |
| `hp` | Angle de profil (°) |
| `theta` | Angle d'incidence (°) |
| `behind` | Soleil derrière le mur ? |
| `d_lat` | Ombre des tableaux latéraux (m) |
| `d_vert` | Ombre du linteau (m) |
| `lit_area_m2` | Surface éclairée (m²) |
| `screen_blocks_all` | Mur écran bloque tout ? |
| `horizon_dip` | Dépression de l'horizon due à l'altitude (°) |
| `desired_position` | Position de store recommandée (0–100) |
| `strategy` | Nom de la stratégie active |
| `cloud_coverage` | Couverture nuageuse (%) — si météo configurée |
| `weather_condition` | État météo (sunny, cloudy, rainy…) |
| `temperature` | Température extérieure (°C) |
| `cover_entity` | Entité cover liée |
| `zone_entity` | Entité zone utilisée |
| `latitude`, `longitude` | Coordonnées utilisées |

## Stratégies de pilotage

La stratégie détermine comment `desired_position` est calculé. Elle est choisie par fenêtre dans la configuration.

| Stratégie | Comportement |
|-----------|-------------|
| **block_all** | Ferme assez pour bloquer tout le soleil direct (été / canicule). Position = `100 × y_ombre / Hw`. |
| **winter_passive** | Chauffage solaire passif : ouvert (100%) si soleil sur la fenêtre, fermé (0%) sinon. |
| **proportional** | `position = 100 − ensoleillement%` : plus il y a de soleil, plus le store descend. |
| **threshold** | Ferme (0%) si ensoleillement ≥ 50%, ouvre (100%) si ≤ 20%. Interpolation linéaire entre les deux. |
| **temperature_guard** | Si température ≥ 28°C et ensoleillement ≥ 20% → applique block_all. Sinon ouvert (100%). |
| **privacy_night** | Fermé (0%) si le soleil est sous l'horizon, ouvert (100%) le jour. |
| **target_illumination** | Maintient exactement 30% d'ensoleillement. Utilise une recherche 5% + binaire pour trouver la position optimale du store. |

De nouvelles stratégies peuvent être ajoutées dans `strategies.py`.

## Automatisations

Utiliser `desired_position` pour piloter un store :

```yaml
alias: "Store salon — position solaire"
trigger:
  - platform: state
    entity_id: sensor.sunny_salon
action:
  - service: cover.set_cover_position
    target:
      entity_id: cover.store_salon
    data:
      position: "{{ state_attr('sensor.sunny_salon', 'desired_position') | int }}"
```

Ou avec une condition sur l'ensoleillement :

```yaml
alias: "Fermer si ensoleillement élevé"
trigger:
  - platform: state
    entity_id: sensor.sunny_salon
condition:
  - condition: numeric_state
    entity_id: sensor.sunny_salon
    above: 40
action:
  - service: cover.set_cover_position
    target:
      entity_id: cover.store_salon
    data:
      position: "{{ state_attr('sensor.sunny_salon', 'desired_position') | int }}"
```

## Simulateur

Un simulateur interactif est fourni dans `simulateur_ensoleillement_fenetre.html`. L'ouvrir dans un navigateur pour :

- Visualiser en plan et en coupe l'ensoleillement d'une fenêtre
- Tester tous les paramètres (orientation, dimensions, mur écran, altitude)
- Se connecter à Home Assistant pour récupérer la position actuelle du soleil
- Placer un marqueur sur une carte OpenStreetMap pour la géolocalisation

## Références

- `FORMULA.md` — détail complet des formules de géométrie solaire
- `ui.md` — description de l'interface du simulateur et limitations connues