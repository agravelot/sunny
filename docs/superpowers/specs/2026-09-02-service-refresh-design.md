# Design — Service `sunny.refresh` à la place du polling

**Date :** 2026-09-02

## Contexte

`SunnyCoordinator` (DataUpdateCoordinator) recalcule l'ensoleillement toutes les
`refresh_interval` minutes (défaut 5). L'utilisateur veut piloter le
rafraîchissement par une automation HA native : l'intégration expose un service
`sunny.refresh` et ne poll plus du tout.

## Décisions

- **Service uniquement** : `update_interval=None`. La donnée est calculée au
  premier refresh (setup) puis uniquement sur appel de `sunny.refresh`.
- **Suppression de l'option `refresh_interval`** : champ retiré du config flow,
  constantes supprimées. Les options stockées existantes gardent un
  `refresh_interval` résiduel, ignoré — pas de migration.
- `async_refresh()` (exécution immédiate) plutôt que `async_request_refresh()`
  (debounce ~30 s) pour un comportement déterministe côté automation.

## Implémentation

- `coordinator.py` : `update_interval=None`, suppression des références à
  `DEFAULT_REFRESH_INTERVAL`.
- `services.py` : `SERVICE_REFRESH = "refresh"`, handler sans champ qui appelle
  `async_refresh()` sur tous les coordinators de `hass.data[DOMAIN]` (support de
  plusieurs entries), enregistré dans `async_register_services`.
- `services.yaml` : entrée `refresh` sans champs (textes en français).
- `config_flow.py` : suppression de `async_step_refresh`, de l'action `refresh`
  du menu OptionsFlow, et de `CONF_REFRESH_INTERVAL` dans le ConfigFlow.
- `strings.json` : suppression du step `refresh` et de l'option sélecteur.
- `const.py` : suppression de `CONF_REFRESH_INTERVAL` et
  `DEFAULT_REFRESH_INTERVAL`.

## Tests

- `test_services.py` : service enregistré ; l'appel déclenche `async_refresh()`
  sur tous les coordinators ; aucun crash sans entry.
- `test_coordinator.py` : `update_interval is None`.

## Hors scope

- Simulateur HTML et `solar_math.py` non affectés.
- Pas de migration des options stockées.
