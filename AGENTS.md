# AGENTS.md

## Langue

Tout le code, les commentaires, la documentation et l'UI sont en **français**. Les messages de commit sont en français.

## Objectif du projet

Créer un **plugin Home Assistant** (custom integration) pour piloter automatiquement des stores/volets en fonction de l'ensoleillement, de la météo et de la saison.

## État actuel

- **Simulateur** : un fichier HTML unique `simulateur_ensoleillement_fenetre.html` (~800 lignes) contenant toute la logique (calcul solaire, ombres, rendu SVG, client API HA, carte Leaflet, persistance localStorage)
- **Docs** : `FORMULA.md` (formules de géométrie solaire), `ui.md` (description et limitations du simulateur)
- **Intégration HA existante** : lecture seule — fetch l'entité `sun.sun`, `zone.home` et `/api/config` pour peupler le simulateur. Aucune écriture vers HA (pas de pilotage de stores).
- **Pas encore de plugin HA** : rien côté Python, pas de `custom_components/`, pas de manifest, pas de `configuration.yaml`
- La **doc développeur Home Assistant** est dispo en local dans `~/lab/developers.home-assistant` (repo officiel `home-assistant/developers.home-assistant`)

## Architecture

- Pas de build, pas de package manager, pas de CI, pas de `.gitignore`
- Le simulateur s'ouvre directement dans un navigateur
- Le futur plugin HA devra extraire le moteur de calcul solaire du HTML et l'embarquer dans une custom integration Python + éventuellement une carte Lovelace

## Conventions Git

- Branche unique `main`
- `pull.rebase = true` configuré
- Messages de commit : français, concis, minuscule, impératif (ex: `add window altitude with horizon dip calculation`)

## Calculs clés

Voir `FORMULA.md` pour les formules complètes. Résumé :

- **Position solaire** : `h` (altitude) et `As` (azimut) calculés via déclinaison + angle horaire (modèle simplifié, sans réfraction ni équation du temps)
- **Écart azimutal** : `γ = As − An`. Si `|γ| ≥ 90°` → soleil derrière le mur
- **Angle de profil** : `tan hp = tan h / cos γ` — utilisé pour toutes les ombres verticales
- **Angle d'incidence** : `cos θ = cos h · cos γ` — pour le calcul d'énergie (loi de Lambert)
- **Ombres d'embrasure** : épaisseur du mur `e` → `d_lat = e · tan(γ)` (tableau), `d_vert = e · tan(hp)` (linteau)
- **Mur écran** : `y_ombre = max(0, min(Hw, Hm − D · tan(hp)))`. Le code actuel **n'utilise pas** le concept de `hp_limite` ; l'ombre est calculée directement par la formule ci-dessus
- **Horizon dip** : `dip = arccos(6371 / (6371 + altitude/1000))` — le soleil est visible quand `h > −dip`