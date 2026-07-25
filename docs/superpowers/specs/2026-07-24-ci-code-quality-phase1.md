# CI Code Quality — Phase 1

Date: 2026-07-24
Statut: Approuvé

## Objectif

Ajouter ruff (lint + format) et yamllint au workflow CI existant pour améliorer la qualité du code Python et YAML.

## Approche

Configuration permissive (`continue-on-error: true`) — les outils signalent les problèmes sans bloquer le merge. Chaque phase successive resserre la tolérance.

## Fichiers à créer

| Fichier | Contenu |
|---------|---------|
| `ruff.toml` | Configuration Ruff (sélection de règles, permissif) |
| `.pre-commit-config.yaml` | Hooks pre-commit (créé maintenant, activé en phase 3) |

## Fichiers à modifier

| Fichier | Changement |
|---------|------------|
| `.github/workflows/validate.yml` | Ajouter un job `quality` parallèle |

## Configuration Ruff (`ruff.toml`)

```toml
target-version = "py313"
line-length = 100

lint.select = ["F", "E", "W", "I", "N", "UP", "YTT"]

lint.ignore = [
    "E501",  # line-too-long — géré par ruff format
    "E741",  # ambiguous-variable-name — trop de single-letter vars existantes
]

[format]
quote-style = "double"
indent-style = "space"
docstring-code-format = false
```

## Nouveau job CI : `quality`

```yaml
quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install ruff yamllint
      - run: ruff check --output-format github
        continue-on-error: true
      - run: ruff format --check
        continue-on-error: true
      - run: yamllint .github/ hacs.json
        continue-on-error: true
```

## Phases ultérieures

| Phase | Contenu | Bloque le merge ? |
|-------|---------|-------------------|
| 1 | Ruff + yamllint | Non (warnings) |
| 2 | MyPy | Non (permissif) |
| 3 | Activer pre-commit | Non |
| 4 | reviewdog pour PR comments | Non |
| 5 | ⬆️ Tout passer en `continue-on-error: false` | Oui |