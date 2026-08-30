# Plan d'implémentation — Stratégie `lux_target_glare`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** Ajouter une stratégie lux anti-éblouissement : ouvrir en priorité les fenêtres sans soleil direct, fermer en priorité les fenêtres ensoleillées, au sein des groupes de fenêtres partageant un capteur lux.

**Architecture :** Nouvelle classe `LuxTargetGlareStrategy` pure dans `strategies.py` (reçoit des flags `can_open`/`can_close`), helper pur `compute_glare_flags` (tiering + saturation), regroupement par capteurs résolus partagés dans le coordinator (`_merge_sensor_groups` + `_apply_lux_glare` en passe 2 de `_async_update_data`), refactor extraction `_resolve_lux_context` préservant le comportement de `lux_target`.

**Tech Stack :** Python 3, pytest (aucun import homeassistant dans les tests ; mocks HA pour coordinator).

## Global Constraints

- Tout le code, commentaires et labels en **français**
- `strategies.py` ne doit **aucun** import `homeassistant.*` (tests l'importent directement)
- Tests : import direct via hack `sys.path` (convention existante des fichiers de tests)
- Commande de vérification : `python3 -m pytest tests/ -v`
- Git : messages concis, impératif, minuscule (ex. `add lux_target_glare strategy`)
- Spec de référence : `docs/superpowers/specs/2026-08-30-lux-glare-strategy-design.md`

---

### Task 1: Stratégie pure `LuxTargetGlareStrategy`

**Files:**
- Modify: `custom_components/sunny/strategies.py` (après `LuxTargetStrategy`, ligne ~331)
- Test: `tests/test_strategies.py` (nouvelle classe à la fin)

**Interfaces:**
- Produces: classe `LuxTargetGlareStrategy` avec `name = "lux_target_glare"`, `label = "Cible lux anti-éblouissement (priorité sans soleil direct)"`, `compute_position(data: dict) -> int`. Lit `can_open`/`can_close` (défaut `True`) dans `data`. Enregistrée dans `STRATEGIES`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_strategies.py` :

```python
# -----------------------------------------------------------------------
# LuxTargetGlareStrategy
# -----------------------------------------------------------------------

class TestLuxTargetGlareStrategy:
    """Tests pour la stratégie lux_target_glare (anti-éblouissement)."""

    def _data(self, **kw) -> dict:
        data = {
            "lux_value": 4000.0,
            "current_position": 50,
            "lux_high": 5000,
            "lux_low": 3000,
            "lux_step": 10,
            "can_open": True,
            "can_close": True,
        }
        data.update(kw)
        return data

    def test_registered(self):
        assert "lux_target_glare" in strategies.STRATEGIES
        assert (
            strategies.STRATEGIES["lux_target_glare"].label
            == "Cible lux anti-éblouissement (priorité sans soleil direct)"
        )

    def test_lux_none_unchanged(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=None)) == 50

    def test_deadzone_unchanged(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=4000)) == 50

    def test_above_high_closes_when_allowed(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=6000)) == 40

    def test_above_high_blocked(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=6000, can_close=False)) == 50

    def test_below_low_opens_when_allowed(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=1000)) == 60

    def test_below_low_blocked(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=1000, can_open=False)) == 50

    def test_open_clamped_at_100(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=1000, current_position=95)) == 100

    def test_close_clamped_at_0(self):
        s = strategies.STRATEGIES["lux_target_glare"]
        assert s.compute_position(self._data(lux_value=6000, current_position=5)) == 0

    def test_flags_default_true(self):
        """Sans flags (usage autonome), se comporte comme lux_target."""
        s = strategies.STRATEGIES["lux_target_glare"]
        data = self._data(lux_value=1000)
        del data["can_open"]
        del data["can_close"]
        assert s.compute_position(data) == 60
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m pytest tests/test_strategies.py::TestLuxTargetGlareStrategy -v`
Expected: FAIL — `KeyError: 'lux_target_glare'` sur `test_registered`

- [ ] **Step 3: Implémenter**

Dans `custom_components/sunny/strategies.py`, après la classe `LuxTargetStrategy` (ligne 331) :

```python
class LuxTargetGlareStrategy(BaseStrategy):
    """Régulation lux anti-éblouissement — priorité aux fenêtres sans soleil direct.

    Les flags can_open / can_close sont calculés par le coordinator pour le
    groupe de fenêtres partageant un capteur lux :
    - ouverture : les fenêtres sans soleil direct d'abord
    - fermeture : les fenêtres ensoleillées d'abord
    """

    name = "lux_target_glare"
    label = "Cible lux anti-éblouissement (priorité sans soleil direct)"

    def compute_position(self, data: dict) -> int:
        lux = data.get("lux_value")
        cur = data.get("current_position", 100)
        high = data.get("lux_high", 5000)
        low = data.get("lux_low", 3000)
        step = data.get("lux_step", 10)
        can_open = data.get("can_open", True)
        can_close = data.get("can_close", True)

        if lux is None:
            return cur

        if lux > high and can_close:
            return max(0, cur - step)
        if lux < low and can_open:
            return min(100, cur + step)
        return cur
```

Et dans le dict `STRATEGIES`, après l'entrée `"lux_target": LuxTargetStrategy(),` :

```python
    "lux_target_glare": LuxTargetGlareStrategy(),
```

- [ ] **Step 4: Vérifier le passage**

Run: `python3 -m pytest tests/test_strategies.py -v`
Expected: PASS (tous, y compris les tests existants)

- [ ] **Step 5: Commit**

```bash
git add custom_components/sunny/strategies.py tests/test_strategies.py
git commit -m "add lux_target_glare strategy"
```

---

### Task 2: Helper pur `compute_glare_flags`

**Files:**
- Modify: `custom_components/sunny/strategies.py` (helper au niveau module, avant la section « Stratégies »)
- Test: `tests/test_strategies.py`

**Interfaces:**
- Produces: `compute_glare_flags(groups: list[list[str]], tiers: dict[str, int], open_margins: dict[str, bool], close_margins: dict[str, bool]) -> dict[str, dict[str, bool]]` — clé = nom de fenêtre, valeur = `{"can_open": bool, "can_close": bool}`. Consommé par le coordinator en Task 5.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_strategies.py` :

```python
# -----------------------------------------------------------------------
# compute_glare_flags
# -----------------------------------------------------------------------

class TestComputeGlareFlags:
    """Tests pour le calcul des flags can_open / can_close.

    Tier 0 = pas de soleil direct, tier 1 = soleil direct.
    """

    def test_singleton_group_open_and_close(self):
        flags = strategies.compute_glare_flags(
            [["A"]], {"A": 0}, {"A": True}, {"A": True}
        )
        assert flags["A"] == {"can_open": True, "can_close": True}

    def test_tier0_opens_first_tier1_blocked(self):
        flags = strategies.compute_glare_flags(
            [["A", "B"]], {"A": 0, "B": 1}, {"A": True, "B": True}, {"A": True, "B": True}
        )
        assert flags["A"] == {"can_open": True, "can_close": False}
        assert flags["B"] == {"can_open": False, "can_close": True}

    def test_tier0_saturated_tier1_opens(self):
        flags = strategies.compute_glare_flags(
            [["A", "B"]], {"A": 0, "B": 1}, {"A": False, "B": True}, {"A": True, "B": True}
        )
        assert flags["A"]["can_open"] is False
        assert flags["B"]["can_open"] is True

    def test_tier1_saturated_tier0_closes(self):
        flags = strategies.compute_glare_flags(
            [["A", "B"]], {"A": 0, "B": 1}, {"A": True, "B": True}, {"A": True, "B": False}
        )
        assert flags["B"]["can_close"] is False
        assert flags["A"]["can_close"] is True

    def test_two_tier0_windows_open_together(self):
        """Expositions similaires : mêmes flags, ouverture simultanée."""
        flags = strategies.compute_glare_flags(
            [["A", "B"]], {"A": 0, "B": 0}, {"A": True, "B": True}, {"A": True, "B": True}
        )
        assert flags["A"]["can_open"] is True
        assert flags["B"]["can_open"] is True

    def test_separate_groups_independent(self):
        flags = strategies.compute_glare_flags(
            [["A"], ["B"]], {"A": 0, "B": 1}, {"A": True, "B": True}, {"A": True, "B": True}
        )
        assert flags["A"] == {"can_open": True, "can_close": True}
        assert flags["B"] == {"can_open": True, "can_close": True}
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m pytest tests/test_strategies.py::TestComputeGlareFlags -v`
Expected: FAIL — `AttributeError: module 'strategies' has no attribute 'compute_glare_flags'`

- [ ] **Step 3: Implémenter**

Dans `custom_components/sunny/strategies.py`, après `search_cover_position` (ligne 187), avant la section « Stratégies » :

```python
def compute_glare_flags(
    groups: list[list[str]],
    tiers: dict[str, int],
    open_margins: dict[str, bool],
    close_margins: dict[str, bool],
) -> dict[str, dict[str, bool]]:
    """Calcule les flags can_open / can_close pour la priorité anti-éblouissement.

    Tier 0 = pas de soleil direct, tier 1 = soleil direct.

    - Ouverture : une fenêtre tier 0 ouvre toujours ; une fenêtre tier 1
      n'ouvre que lorsqu'aucune fenêtre tier 0 de son groupe n'a de marge.
    - Fermeture : une fenêtre tier 1 ferme toujours ; une fenêtre tier 0 ne
      ferme que lorsqu'aucune fenêtre tier 1 de son groupe n'a de marge.
    """
    flags: dict[str, dict[str, bool]] = {}
    for group in groups:
        tier0 = [n for n in group if tiers.get(n, 0) == 0]
        tier1 = [n for n in group if tiers.get(n, 0) == 1]
        tier0_saturated_open = all(not open_margins.get(n, False) for n in tier0)
        tier1_saturated_close = all(not close_margins.get(n, False) for n in tier1)
        for name in group:
            tier = tiers.get(name, 0)
            flags[name] = {
                "can_open": tier == 0 or tier0_saturated_open,
                "can_close": tier == 1 or tier1_saturated_close,
            }
    return flags
```

- [ ] **Step 4: Vérifier le passage**

Run: `python3 -m pytest tests/test_strategies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/sunny/strategies.py tests/test_strategies.py
git commit -m "add glare priority flags computation"
```

---

### Task 3: Regroupement `_merge_sensor_groups` (coordinator)

**Files:**
- Modify: `custom_components/sunny/coordinator.py` (fonction module, après `_LOGGER`)
- Test: `tests/test_coordinator.py` (nouvelle classe à la fin)

**Interfaces:**
- Produces: `_merge_sensor_groups(resolved: dict[str, set[str]]) -> list[list[str]]` — groupes de noms de fenêtres fusionnés par intersection (directe ou en chaîne) des ensembles de capteurs.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_coordinator.py` :

```python
# ---------------------------------------------------------------------------
# Tests _merge_sensor_groups
# ---------------------------------------------------------------------------

class TestMergeSensorGroups:
    """Tests pour le regroupement par capteurs résolus partagés."""

    def test_no_intersection_separate(self):
        resolved = {"Grand": {"s1"}, "Cuisine": {"s2"}}
        assert coordinator_module._merge_sensor_groups(resolved) == [["Grand"], ["Cuisine"]]

    def test_shared_sensor_merged(self):
        """Salon (area) + cuisine (manuelle) résolvent la même entité → même groupe."""
        resolved = {"Grand": {"sensor.salon_lux"}, "Cuisine": {"sensor.salon_lux"}}
        assert coordinator_module._merge_sensor_groups(resolved) == [["Grand", "Cuisine"]]

    def test_chained_merge(self):
        resolved = {"A": {"s1"}, "B": {"s1", "s2"}, "C": {"s2"}}
        groups = coordinator_module._merge_sensor_groups(resolved)
        assert sorted(groups) == [["A", "B", "C"]]

    def test_empty_sensors_never_merge(self):
        resolved = {"A": set(), "B": set()}
        assert coordinator_module._merge_sensor_groups(resolved) == [["A"], ["B"]]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m pytest tests/test_coordinator.py::TestMergeSensorGroups -v`
Expected: FAIL — `AttributeError: ... has no attribute '_merge_sensor_groups'`

- [ ] **Step 3: Implémenter**

Dans `custom_components/sunny/coordinator.py`, après la ligne `_LOGGER = logging.getLogger(__name__)` :

```python
def _merge_sensor_groups(resolved: dict[str, set[str]]) -> list[list[str]]:
    """Fusionne les fenêtres partageant au moins un capteur lux résolu.

    Chaque groupe est une liste de noms de fenêtres. Deux fenêtres dont les
    ensembles de capteurs s'intersectent — directement ou via une chaîne —
    finissent dans le même groupe.
    """
    groups = [[name] for name in resolved]
    changed = True
    while changed:
        changed = False
        for i in range(len(groups)):
            merged = False
            for j in range(i + 1, len(groups)):
                if any(resolved[a] & resolved[b] for a in groups[i] for b in groups[j]):
                    groups[i].extend(groups[j])
                    del groups[j]
                    merged = True
                    changed = True
                    break
            if merged:
                break
    return groups
```

- [ ] **Step 4: Vérifier le passage**

Run: `python3 -m pytest tests/test_coordinator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/sunny/coordinator.py tests/test_coordinator.py
git commit -m "add lux sensor group merging"
```

---

### Task 4: Refactor `_resolve_lux_context` (comportement préservé)

**Files:**
- Modify: `custom_components/sunny/coordinator.py:107-199` (remplacement de `_compute_lux_target_position`)
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Produces: `_resolve_lux_context(win: dict) -> dict` avec clés `"lux"` (float | None), `"fallback"` (int), `"current_position"` (int), `"sensors"` (set[str]). `_compute_lux_target_position(win, strategy) -> int` garde sa signature et son comportement (tests existants `TestComputeLuxTargetStale` et `TestComputeLuxTargetPreviousDesired` doivent rester verts sans modification).

- [ ] **Step 1: Écrire le test du contexte (échoue d'abord)**

Ajouter à la fin de `tests/test_coordinator.py` :

```python
# ---------------------------------------------------------------------------
# Tests _resolve_lux_context
# ---------------------------------------------------------------------------

class TestResolveLuxContext:
    """Tests pour la résolution du contexte lux (refactor de _compute_lux_target_position)."""

    NOW = datetime(2026, 7, 25, 18, 40, 0, tzinfo=timezone.utc)

    def _states(self, mock_hass, cover_position, cover_state_value="open", sensor_lux="0"):
        cover_last_changed = self.NOW - timedelta(hours=2)
        cover_state = _make_mock_state(
            cover_state_value, cover_last_changed, cover_last_changed,
            {"current_position": cover_position},
        )
        mapping = {"cover.test": cover_state}
        if sensor_lux is not None:
            sensor_last_updated = self.NOW - timedelta(hours=4)
            mapping["sensor.lux_salon"] = _make_mock_state(
                sensor_lux, sensor_last_updated, sensor_last_updated,
                {"device_class": "illuminance"},
            )
        mock_hass.states.get.side_effect = lambda eid: mapping.get(eid)

    def _compute(self, coordinator_instance, win):
        with patch("sunny.coordinator.datetime") as mock_dt:
            mock_dt.now.return_value = self.NOW
            mock_dt.timezone = timezone
            mock_dt.timedelta = timedelta
            return coordinator_instance._resolve_lux_context(win)

    def test_fresh_lux_with_sensors(self, coordinator_instance, mock_hass):
        self._states(mock_hass, cover_position=50, sensor_lux="4000")
        win = {"name": "Salon", "cover_entity": "cover.test",
               "lux_sensors": ["sensor.lux_salon"]}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["lux"] == 4000.0
        assert ctx["current_position"] == 50
        assert ctx["sensors"] == {"sensor.lux_salon"}

    def test_no_sensors_lux_none(self, coordinator_instance, mock_hass):
        self._states(mock_hass, cover_position=50, sensor_lux=None)
        win = {"name": "Salon", "cover_entity": "cover.test", "lux_sensors": []}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["lux"] is None
        assert ctx["sensors"] == set()

    def test_moving_cover_lux_none_and_previous_fallback(self, coordinator_instance, mock_hass):
        sensor_last_updated = self.NOW - timedelta(hours=4)
        sensor_state = _make_mock_state(
            "0", sensor_last_updated, sensor_last_updated, {"device_class": "illuminance"},
        )
        cover_state = _make_mock_state("opening", self.NOW, self.NOW, {"current_position": 95})
        mock_hass.states.get.side_effect = lambda eid: {
            "cover.test": cover_state, "sensor.lux_salon": sensor_state,
        }.get(eid)
        coordinator_instance.data = {"Salon": {"desired_position": 90}}
        win = {"name": "Salon", "cover_entity": "cover.test",
               "lux_sensors": ["sensor.lux_salon"]}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["lux"] is None
        assert ctx["fallback"] == 90

    def test_no_previous_data_fallback_is_current(self, coordinator_instance, mock_hass):
        self._states(mock_hass, cover_position=50, sensor_lux=None)
        coordinator_instance.data = {}
        win = {"name": "Salon", "cover_entity": "cover.test", "lux_sensors": []}
        ctx = self._compute(coordinator_instance, win)
        assert ctx["fallback"] == 50
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m pytest tests/test_coordinator.py::TestResolveLuxContext -v`
Expected: FAIL — `AttributeError: ... has no attribute '_resolve_lux_context'`

- [ ] **Step 3: Refactorer (extraire, ne rien changer au comportement)**

Remplacer intégralement `_compute_lux_target_position` (coordinator.py:107-199) par :

```python
    def _resolve_lux_context(self, win: dict) -> dict:
        """Résout le contexte lux d'une fenêtre.

        Retourne un dict avec :
        - "lux" : valeur lux agrégée, ou None si capteur indisponible/stale
          ou volet en mouvement
        - "fallback" : position de repli (snapshot précédent si disponible,
          sinon position courante du volet)
        - "current_position" : position courante du volet (100 si inconnue)
        - "sensors" : ensemble des capteurs lux résolus
        """
        name = win.get("name", "Fenêtre")
        cover_entity = win.get("cover_entity", "")
        cover_state = self.hass.states.get(cover_entity)
        current_position = 100
        cover_last_changed = None
        if cover_state is not None:
            pos = cover_state.attributes.get("current_position")
            if pos is not None:
                try:
                    current_position = int(float(pos))
                except (ValueError, TypeError):
                    pass
            cover_last_changed = cover_state.last_changed

        previous_desired = self._previous_desired(name)
        fallback = previous_desired if previous_desired is not None else current_position

        # Volet en mouvement : la position instantanée ne correspondra pas à
        # la position d'arrêt et le capteur lux ne reflète pas la position
        # finale → conserver le snapshot précédent pour éviter que le switch
        # ne prenne le settle pour une intervention manuelle.
        if cover_state is not None and str(cover_state.state) in ("opening", "closing", "moving"):
            return {
                "lux": None,
                "fallback": fallback,
                "current_position": current_position,
                "sensors": set(),
            }

        sensor_ids = self._resolve_lux_sensors(win)
        if not sensor_ids:
            _LOGGER.warning(
                "Aucun capteur lux trouvé pour la fenêtre '%s' (lux_sensors=%s, lux_area_id=%s)",
                name,
                win.get("lux_sensors", []),
                win.get("lux_area_id"),
            )
            return {
                "lux": None,
                "fallback": fallback,
                "current_position": current_position,
                "sensors": set(),
            }

        fresh_values = []
        stale_count = 0
        for sid in sensor_ids:
            sensor_state = self.hass.states.get(sid)
            if sensor_state is None:
                _LOGGER.debug("Capteur lux '%s' introuvable", sid)
                continue
            if cover_last_changed is not None:
                now = datetime.now(timezone.utc)
                grace = int((now - cover_last_changed).total_seconds())
                if grace < 60:
                    stale_count += 1
                    _LOGGER.debug(
                        "Capteur lux '%s' stale (couverture en pause %ds/60s après mouvement du volet)",
                        sid, grace,
                    )
                    continue
            try:
                val = float(sensor_state.state)
                fresh_values.append(val)
                _LOGGER.debug(
                    "Capteur lux '%s' frais : %s lx (last_updated=%s)",
                    sid, val, sensor_state.last_updated,
                )
            except (ValueError, TypeError):
                _LOGGER.debug("Capteur lux '%s' valeur non numérique: %s", sid, sensor_state.state)

        if not fresh_values:
            _LOGGER.info(
                "Aucun capteur frais pour la fenêtre '%s' (%d stale sur %d), position inchangée à %d",
                name, stale_count, len(sensor_ids), fallback,
            )
            return {
                "lux": None,
                "fallback": fallback,
                "current_position": current_position,
                "sensors": set(sensor_ids),
            }

        lux_value = sum(fresh_values) / len(fresh_values)
        _LOGGER.debug(
            "Lux agrégé pour '%s': %.0f lx (moyenne de %d capteurs)",
            name, lux_value, len(fresh_values),
        )
        return {
            "lux": lux_value,
            "fallback": fallback,
            "current_position": current_position,
            "sensors": set(sensor_ids),
        }

    def _compute_lux_target_position(self, win: dict, strategy) -> int:
        """Calcule la position pour une fenêtre en stratégie lux_target.

        Retourne la position inchangée si aucun capteur frais.
        """
        ctx = self._resolve_lux_context(win)
        lux = ctx["lux"]
        if lux is None:
            return ctx["fallback"]

        data = {
            "lux_value": lux,
            "current_position": ctx["current_position"],
            "lux_high": win.get("lux_high", DEFAULT_LUX_HIGH),
            "lux_low": win.get("lux_low", DEFAULT_LUX_LOW),
            "lux_step": win.get("lux_step", DEFAULT_LUX_STEP),
        }
        new_position = strategy.compute_position(data)
        if new_position != ctx["current_position"]:
            _LOGGER.info(
                "Lux target '%s': lux=%.0f lx, position %d → %d",
                win.get("name", "Inconnue"), lux, ctx["current_position"], new_position,
            )
        return new_position
```

- [ ] **Step 4: Vérifier — nouveaux tests ET régression existante**

Run: `python3 -m pytest tests/test_coordinator.py -v`
Expected: PASS — nouveaux tests `TestResolveLuxContext` + tous les tests existants (`TestComputeLuxTargetStale`, `TestComputeLuxTargetPreviousDesired`) restent verts sans modification

- [ ] **Step 5: Commit**

```bash
git add custom_components/sunny/coordinator.py tests/test_coordinator.py
git commit -m "refactor lux context resolution"
```

---

### Task 5: Arbitrage `_apply_lux_glare` + intégration passe 2

**Files:**
- Modify: `custom_components/sunny/coordinator.py` (méthode `_apply_lux_glare` dans la classe, après `_compute_lux_target_position` ; import `compute_glare_flags` ligne 37 ; dispatch dans `_async_update_data` lignes 227-282)
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `_resolve_lux_context` (Task 4), `_merge_sensor_groups` (Task 3), `compute_glare_flags` (Task 2), `get_strategy("lux_target_glare")` (Task 1)
- Produces: `SunnyCoordinator._apply_lux_glare(lux_ctx: dict, results: dict, windows: list) -> None` — écrit `results[name]["desired_position"]` (clampé min/max) pour chaque fenêtre de `lux_ctx`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_coordinator.py` :

```python
# ---------------------------------------------------------------------------
# Tests _apply_lux_glare — arbitrage anti-éblouissement par groupe
# ---------------------------------------------------------------------------

class TestApplyLuxGlare:
    """Scénario réel : grand (ouest), petit salon (sud) et cuisine (sud)
    partagent le capteur lux du salon."""

    def _windows(self):
        return [
            {"name": "Grand", "cover_entity": "cover.grand",
             "strategy": "lux_target_glare", "lux_sensors": ["sensor.salon_lux"]},
            {"name": "Petit salon", "cover_entity": "cover.petit",
             "strategy": "lux_target_glare", "lux_area_id": "salon"},
            {"name": "Cuisine", "cover_entity": "cover.cuisine",
             "strategy": "lux_target_glare", "lux_sensors": ["sensor.salon_lux"]},
        ]

    def _results(self):
        return {
            "Grand": {"lit_pct": 0.0, "strategy": "lux_target_glare"},
            "Petit salon": {"lit_pct": 60.0, "strategy": "lux_target_glare"},
            "Cuisine": {"lit_pct": 55.0, "strategy": "lux_target_glare"},
        }

    def _ctx(self, lux=1000.0):
        """Contexte lux : les 3 fenêtres résolvent sensor.salon_lux."""
        def _one(pos=50):
            return {"lux": lux, "fallback": pos, "current_position": pos,
                    "sensors": {"sensor.salon_lux"}}
        return {
            "Grand": _one(),
            "Petit salon": _one(),
            "Cuisine": _one(),
        }

    def test_too_dark_tier0_opens_tier1_holds(self, coordinator_instance):
        """Trop sombre : le grand (sans soleil direct) ouvre, les autres tiennent."""
        coordinator_instance.data = {}
        results = self._results()
        coordinator_instance._apply_lux_glare(self._ctx(1000.0), results, self._windows())
        assert results["Grand"]["desired_position"] == 60
        assert results["Petit salon"]["desired_position"] == 50
        assert results["Cuisine"]["desired_position"] == 50

    def test_too_dark_tier0_saturated_tier1_open_together(self, coordinator_instance):
        """Grand saturé à 100 : petit salon ET cuisine ouvrent ensemble."""
        coordinator_instance.data = {"Grand": {"desired_position": 100}}
        results = self._results()
        coordinator_instance._apply_lux_glare(self._ctx(1000.0), results, self._windows())
        assert results["Grand"]["desired_position"] == 100
        assert results["Petit salon"]["desired_position"] == 60
        assert results["Cuisine"]["desired_position"] == 60

    def test_too_bright_tier1_closes_tier0_holds(self, coordinator_instance):
        """Trop clair : les fenêtres ensoleillées ferment, le grand tient."""
        coordinator_instance.data = {}
        results = self._results()
        coordinator_instance._apply_lux_glare(self._ctx(6000.0), results, self._windows())
        assert results["Grand"]["desired_position"] == 50
        assert results["Petit salon"]["desired_position"] == 40
        assert results["Cuisine"]["desired_position"] == 40

    def test_too_bright_tier1_saturated_tier0_closes(self, coordinator_instance):
        """Ensoleillées déjà fermées : le grand ferme à son tour."""
        coordinator_instance.data = {
            "Grand": {"desired_position": 50},
            "Petit salon": {"desired_position": 0},
            "Cuisine": {"desired_position": 0},
        }
        results = self._results()
        coordinator_instance._apply_lux_glare(self._ctx(6000.0), results, self._windows())
        assert results["Grand"]["desired_position"] == 40
        assert results["Petit salon"]["desired_position"] == 0
        assert results["Cuisine"]["desired_position"] == 0

    def test_lux_none_fallback_for_all(self, coordinator_instance):
        """Pas de capteur frais : position de repli, quel que soit le tier."""
        coordinator_instance.data = {}
        ctx = self._ctx(lux=None)
        results = self._results()
        coordinator_instance._apply_lux_glare(ctx, results, self._windows())
        assert results["Grand"]["desired_position"] == 50
        assert results["Petit salon"]["desired_position"] == 50
        assert results["Cuisine"]["desired_position"] == 50

    def test_no_sensor_window_is_singleton(self, coordinator_instance):
        """Fenêtre sans capteur résolu : groupe singleton, repli sur fallback."""
        coordinator_instance.data = {}
        ctx = {
            "Isolée": {"lux": None, "fallback": 42, "current_position": 30,
                       "sensors": set()},
        }
        results = {"Isolée": {"lit_pct": 0.0, "strategy": "lux_target_glare"}}
        windows = [{"name": "Isolée", "cover_entity": "cover.x",
                    "strategy": "lux_target_glare", "lux_sensors": []}]
        coordinator_instance._apply_lux_glare(ctx, results, windows)
        assert results["Isolée"]["desired_position"] == 42

    def test_respects_max_position_clamp(self, coordinator_instance):
        """Le clamp min/max de la fenêtre s'applique après la stratégie."""
        coordinator_instance.data = {}
        windows = self._windows()
        windows[0]["max_position"] = 55  # Grand plafonné à 55
        ctx = self._ctx(1000.0)
        ctx["Grand"]["current_position"] = 50
        results = self._results()
        coordinator_instance._apply_lux_glare(ctx, results, windows)
        assert results["Grand"]["desired_position"] == 55
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python3 -m pytest tests/test_coordinator.py::TestApplyLuxGlare -v`
Expected: FAIL — `AttributeError: ... has no attribute '_apply_lux_glare'`

- [ ] **Step 3: Implémenter**

3a. Modifier l'import ligne 37 de `custom_components/sunny/coordinator.py` :

```python
from .strategies import compute_glare_flags, get_strategy
```

3b. Ajouter la méthode dans la classe `SunnyCoordinator`, après `_compute_lux_target_position` :

```python
    def _apply_lux_glare(self, lux_ctx: dict, results: dict, windows: list) -> None:
        """Calcule desired_position des fenêtres en stratégie lux_target_glare.

        Regroupe les fenêtres partageant au moins un capteur lux résolu, puis
        applique la priorité anti-éblouissement : ouverture des fenêtres sans
        soleil direct en premier, fermeture des fenêtres ensoleillées en
        premier. Les fenêtres d'exposition similaire bougent ensemble.
        """
        strategy = get_strategy("lux_target_glare")
        wins_by_name = {w.get("name", "Fenêtre"): w for w in windows}
        resolved = {name: ctx["sensors"] for name, ctx in lux_ctx.items()}
        groups = _merge_sensor_groups(resolved)

        tiers = {
            name: (0 if results[name].get("lit_pct", 0) == 0 else 1)
            for name in lux_ctx
        }
        open_margins: dict[str, bool] = {}
        close_margins: dict[str, bool] = {}
        bounds: dict[str, tuple[int, int]] = {}
        for name in lux_ctx:
            win = wins_by_name.get(name, {})
            min_pos = int(win.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION))
            max_pos = int(win.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION))
            bounds[name] = (min_pos, max_pos)
            prev = self._previous_desired(name)
            # Premier cycle sans historique : marge considérée disponible
            open_margins[name] = True if prev is None else prev < max_pos
            close_margins[name] = True if prev is None else prev > min_pos

        flags = compute_glare_flags(groups, tiers, open_margins, close_margins)

        for name, ctx in lux_ctx.items():
            win = wins_by_name.get(name, {})
            min_pos, max_pos = bounds[name]
            lux = ctx["lux"]
            if lux is None:
                new_position = ctx["fallback"]
            else:
                data = {
                    "lux_value": lux,
                    "current_position": ctx["current_position"],
                    "lux_high": win.get(CONF_LUX_HIGH, DEFAULT_LUX_HIGH),
                    "lux_low": win.get(CONF_LUX_LOW, DEFAULT_LUX_LOW),
                    "lux_step": win.get(CONF_LUX_STEP, DEFAULT_LUX_STEP),
                    "can_open": flags[name]["can_open"],
                    "can_close": flags[name]["can_close"],
                }
                new_position = strategy.compute_position(data)
                _LOGGER.debug(
                    "Lux glare '%s': lux=%.0f lx, tier=%d, can_open=%s, can_close=%s",
                    name, lux, tiers[name], flags[name]["can_open"], flags[name]["can_close"],
                )
            results[name]["desired_position"] = max(min_pos, min(max_pos, new_position))
            if results[name]["desired_position"] != ctx["current_position"]:
                _LOGGER.info(
                    "Lux glare '%s': lux=%s, position %d → %d",
                    name,
                    f"{lux:.0f} lx" if lux is not None else "n/a",
                    ctx["current_position"],
                    results[name]["desired_position"],
                )
```

3c. Dans `_async_update_data`, remplacer le bloc de dispatch (lignes 273-282) :

```python
            strategy_name = win.get("strategy", "block_all")
            strategy = get_strategy(strategy_name)
            data["strategy"] = strategy_name
            if strategy_name == "lux_target":
                data["desired_position"] = self._compute_lux_target_position(win, strategy)
            else:
                data["desired_position"] = strategy.compute_position(data)
            min_pos = int(win.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION))
            max_pos = int(win.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION))
            data["desired_position"] = max(min_pos, min(max_pos, data["desired_position"]))
```

par :

```python
            strategy_name = win.get("strategy", "block_all")
            strategy = get_strategy(strategy_name)
            data["strategy"] = strategy_name
            if strategy_name == "lux_target_glare":
                # Passe 2 : arbitrage par groupe de capteurs partagés
                lux_ctx[name] = self._resolve_lux_context(win)
            elif strategy_name == "lux_target":
                data["desired_position"] = self._compute_lux_target_position(win, strategy)
            else:
                data["desired_position"] = strategy.compute_position(data)
            if strategy_name != "lux_target_glare":
                min_pos = int(win.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION))
                max_pos = int(win.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION))
                data["desired_position"] = max(min_pos, min(max_pos, data["desired_position"]))
```

3d. Déclarer `lux_ctx` avant la boucle des fenêtres (après `results = {}`, ligne 227) :

```python
        results = {}
        lux_ctx: dict[str, dict] = {}
```

3e. Appeler la passe 2 après la boucle, avant `return results` (fin de `_async_update_data`) :

```python
        if lux_ctx:
            self._apply_lux_glare(lux_ctx, results, windows)

        return results
```

- [ ] **Step 4: Vérifier le passage**

Run: `python3 -m pytest tests/test_coordinator.py tests/test_strategies.py -v`
Expected: PASS (nouveaux tests `TestApplyLuxGlare` + régression complète des deux fichiers)

- [ ] **Step 5: Commit**

```bash
git add custom_components/sunny/coordinator.py tests/test_coordinator.py
git commit -m "add lux glare group arbitration"
```

---

### Task 6: Vérification complète + mise à jour AGENTS.md

**Files:**
- Modify: `AGENTS.md` (compteur de tests dans la section Commands)

- [ ] **Step 1: Lancer la suite complète**

Run: `python3 -m pytest tests/ -v`
Expected: PASS — 0 échec. Noter le nombre total de tests affiché (ex. `249 passed`).

- [ ] **Step 2: Mettre à jour le compteur dans AGENTS.md**

Dans la section `## Commands`, remplacer le commentaire de la commande pytest par le nouveau nombre (issu de l'étape 1) et ajouter `coordinator` à la liste si absent :

```bash
python3 -m pytest tests/ -v    # <N> unit tests (solar_math + strategies + switch + number + button + services + coordinator)
```

- [ ] **Step 3: Vérifier la non-régression sélective lux_target existant**

Run: `python3 -m pytest tests/test_coordinator.py::TestComputeLuxTargetStale tests/test_coordinator.py::TestComputeLuxTargetPreviousDesired tests/test_strategies.py::TestLuxTargetStrategy -v`
Expected: PASS — le comportement de `lux_target` est inchangé

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "update test count in agents.md"
```
