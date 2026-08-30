# Spec — Stratégie `lux_target_glare` (anti-éblouissement)

Date : 2026-08-30

## Objectif

Régulation lux multi-volets partageant un capteur : privilégier l'ouverture des fenêtres **sans soleil direct** (lumière indirecte) pour limiter l'éblouissement, en acceptant un glare résiduel une fois les fenêtres protégées saturées. Fermeture symétrique : les fenêtres ensoleillées ferment en premier.

## Contexte

Cas d'usage réel : 3 volets partagent le capteur lux du salon —

- 2 volets salon (grand orienté ouest, petit salon orienté sud) : `lux_area_id` = pièce salon
- 1 volet cuisine (orienté sud) : `lux_sensors` manuel pointant le capteur du salon (la cuisine n'a pas de pièce HA avec capteur)

L'existant `lux_target` bouge tous les volets d'un même pas dans la même direction à chaque cycle, sans considération de l'exposition solaire propre à chaque fenêtre.

## Stratégie (strategies.py — pure, testable sans HA)

Classe `LuxTargetGlareStrategy` :

- `name = "lux_target_glare"`
- `label = "Cible lux anti-éblouissement (priorité sans soleil direct)"`
- Enregistrée dans `STRATEGIES` (apparaît automatiquement dans le select par fenêtre via `STRATEGY_OPTIONS`)

Entrées dans `data` :

- Existantes : `lux_value`, `current_position`, `lux_high`, `lux_low`, `lux_step`
- Nouvelles (calculées par le coordinator) : `can_open`, `can_close`

Logique :

- `lux is None` → position courante (inchangé)
- `lux > lux_high` et `can_close` → `max(0, cur - step)` ; sinon position courante
- `lux < lux_low` et `can_open` → `min(100, cur + step)` ; sinon position courante
- Zone morte (`lux_low <= lux <= lux_high`) → position courante

## Flags `can_open` / `can_close` (coordinator.py)

Tier par fenêtre, codé en dur :

- **Tier 0** : pas de soleil direct — `lit_pct == 0` (inclut `behind`, déjà `lit_pct = 0`)
- **Tier 1** : soleil direct — `lit_pct > 0`

Définitions :

- **Ouverture** : `can_open = (tier == 0) OU (aucune fenêtre tier 0 du groupe n'a de marge)` où marge = `previous_desired < max_position`
- **Fermeture** : `can_close = (tier == 1) OU (aucune fenêtre tier 1 du groupe n'a de marge)` où marge = `previous_desired > min_position`

Cas limites :

- `previous_desired is None` (1er cycle) → considéré **avec** marge
- Fenêtre seule dans son groupe → `can_open = can_close = True` (comportement équivalent à `lux_target`)
- `previous_desired` est la valeur déjà clampée min/max du cycle précédent (déjà stockée par le coordinator)

## Regroupement (coordinator.py)

- Refactor de `_compute_lux_target_position` : séparer la résolution/agrégation lux (retourne `lux_value` ou None, conserve les flags stale/mouvement existants) du calcul de position
- `_async_update_data` en 2 passes :
  - **Passe 1** (inchangée) : calcul solaire par fenêtre (`compute_window` → `lit_pct`, `behind`) + résolution/agrégation lux
  - **Passe 2** (nouvelle) : pour les fenêtres en stratégie lux — union des fenêtres dont les **ensembles de capteurs résolus** s'intersectent (gère salon par `lux_area_id` + cuisine par `lux_sensors` manuel pointant le capteur salon), calcul des flags `can_open`/`can_close`, puis position désirée
- Clamp min/max existant appliqué après la stratégie
- Fenêtre lux sans capteur résolu → fallback actuel (position inchangée, log d'avertissement existant conservé)

## UX

- Aucun nouveau champ de configuration : sélection via le select par fenêtre existant, réutilise `lux_high` / `lux_low` / `lux_step`
- `lux_target` actuel intact — zéro régression
- Simulateur HTML non concerné (moteur solaire inchangé, la stratégie est au-dessus)

## Tests (~12 nouveaux)

- Strategy pure : gating par `can_open`/`can_close`, pas ±step, `lux is None`, zone morte
- Coordinator : regroupement par intersection de capteurs résolus (salon-area + cuisine-manuelle dans le même groupe), tiering `lit_pct`, saturation max/min, 1er cycle `None`, fallback sans capteur, groupe singleton

## Hors périmètre

- Tiers multiples (> 2)
- Seuil de tier configurable
- Arbitrage d'un seul mouvant par cycle (le `stagger_delay` existant gère la simultanéité des commandes)
