# CI Code Quality — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ruff (lint + format) and yamllint to the CI workflow with permissive configuration.

**Architecture:** Single new `quality` job in the existing workflow, parallel to `validate-hacs`, `validate-hassfest`, and `test` jobs. Ruff and yamllint run with `continue-on-error: true` so they produce annotations without blocking merge.

**Tech Stack:** ruff, yamllint, GitHub Actions

## Global Constraints

- All config in `ruff.toml` (not `pyproject.toml`)
- Ruff in permissive mode (`continue-on-error: true`)
- New `quality` job runs in parallel, not sequentially
- Python version: 3.13 (matching existing test job)
- Output format: `github` for native PR annotations

---

### Task 1: Create ruff.toml

**Files:**
- Create: `ruff.toml`

**Interfaces:**
- Produces: `ruff.toml` — config consumed by `ruff check` and `ruff format` commands

- [ ] **Step 1: Create ruff.toml**

```toml
target-version = "py313"
line-length = 100

lint.select = [
    "F",    # pyflakes — bugs
    "E",    # pycodestyle — errors
    "W",    # pycodestyle — warnings
    "I",    # isort — import ordering
    "N",    # pep8-naming — naming conventions
    "UP",   # pyupgrade — modern Python syntax
    "YTT",  # flake8-2020 — hardcoded years
]

lint.ignore = [
    "E501",  # line-too-long — handled by ruff format
    "E741",  # ambiguous-variable-name — too many single-letter vars
]

[format]
quote-style = "double"
indent-style = "space"
docstring-code-format = false
```

- [ ] **Step 2: Commit**

```bash
git add ruff.toml
git commit -m "feat: add ruff config"
```

---

### Task 2: Add quality job to CI workflow

**Files:**
- Modify: `.github/workflows/validate.yml` (append `quality` job)

**Interfaces:**
- Consumes: `ruff.toml` from Task 1
- Produces: CI pipeline with quality checks, GitHub Annotations output

- [ ] **Step 1: Add quality job to validate.yml**

Read current validate.yml and append after the existing `test:` job (line 38). Add the following block:

```yaml
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install ruff yamllint
      - name: Ruff lint check
        run: ruff check --output-format github
        continue-on-error: true
      - name: Ruff format check
        run: ruff format --check
        continue-on-error: true
      - name: YAML lint
        run: yamllint .github/ hacs.json
        continue-on-error: true
```

- [ ] **Step 2: Verify final file looks correct**

Run: `head -70 .github/workflows/validate.yml` — confirm indentation, no typos, `continue-on-error` under each step not at job level.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "feat: add ruff and yamllint quality job to CI"
```

---

### Task 3: Create pre-commit config (scaffold only)

**Files:**
- Create: `.pre-commit-config.yaml`

**Interfaces:**
- Produces: `.pre-commit-config.yaml` — hooks file for future activation (phase 3)

- [ ] **Step 1: Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

- [ ] **Step 2: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "feat: add pre-commit config scaffold"
```