# Sunny

Intégration Home Assistant pour le pilotage solaire des stores et volets.

## Fonctionnalités

- Calcule le pourcentage d'ensoleillement direct sur une fenêtre
- Prend en compte l'orientation de la façade, l'épaisseur du mur (embrasure), les obstructions extérieures (mur écran) et l'altitude
- Intègre les données météo (couverture nuageuse, température, condition) pour enrichir les capteurs
- Crée un capteur par fenêtre avec tous les attributs (gamma, hp, theta, ombres, etc.)
- Paramètres éditables via l'interface de configuration HA

## Installation

### Via HACS (custom repository)

1. Dans HACS, ajouter un dépôt personnalisé : `https://github.com/agravelot/sunny` (type : Integration)
2. Installer l'intégration Sunny
3. Redémarrer Home Assistant

### Manuellement

Copier le dossier `custom_components/sunny` dans le répertoire `custom_components` de Home Assistant.

## Configuration

1. Aller dans Paramètres → Appareils et services → Ajouter une intégration → Sunny
2. Sélectionner une entité météo (optionnelle)
3. Ajouter une ou plusieurs fenêtres avec leurs paramètres (orientation, dimensions, store lié, etc.)
4. Les capteurs `sensor.sunny_*` sont créés automatiquement

## Automatisations

Utiliser les capteurs dans des automatisations Home Assistant :

```yaml
- alias: "Fermer le store salon si ensoleillé"
  trigger:
    - platform: state
      entity_id: sensor.sunny_salon
  condition:
    - condition: numeric_state
      entity_id: sensor.sunny_salon
      above: 40
  action:
    - service: cover.close_cover
      target:
        entity_id: cover.store_salon
```

## Simulateur

Un simulateur interactif est fourni dans `simulateur_ensoleillement_fenetre.html` — ouvrir dans un navigateur pour visualiser l'ensoleillement d'une fenêtre et tester les paramètres.