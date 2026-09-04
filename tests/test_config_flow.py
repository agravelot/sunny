"""Tests unitaires pour la validation du config flow Sunny."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "sunny"
sys.path.insert(0, str(SRC.parent))


# ---------------------------------------------------------------------------
# Mocks des modules Home Assistant (import de config_flow uniquement)
# ---------------------------------------------------------------------------

class _MockConfigFlow:
    def __init_subclass__(cls, **kwargs):
        pass


class _MockOptionsFlow:
    pass


def _setup_ha_mocks():
    ha_core = MagicMock()
    ha_core.HomeAssistant = MagicMock
    ha_core.callback = lambda f: f

    ha_config_entries = MagicMock()
    ha_config_entries.ConfigFlow = _MockConfigFlow
    ha_config_entries.OptionsFlow = _MockOptionsFlow

    ha_entity_registry = MagicMock()
    ha_device_registry = MagicMock()

    ha_helpers = MagicMock()
    ha_helpers.entity_registry = ha_entity_registry
    ha_helpers.device_registry = ha_device_registry

    ha_selector = MagicMock()
    ha_selector.AreaSelector = MagicMock
    ha_selector.AreaSelectorConfig = MagicMock
    ha_selector.EntitySelector = MagicMock
    ha_selector.EntitySelectorConfig = MagicMock
    ha_selector.NumberSelector = MagicMock
    ha_selector.NumberSelectorConfig = MagicMock
    ha_selector.NumberSelectorMode = MagicMock

    ha = MagicMock()
    ha.helpers = ha_helpers
    ha.core = ha_core
    ha.config_entries = ha_config_entries

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.entity_registry"] = ha_entity_registry
    sys.modules["homeassistant.helpers.device_registry"] = ha_device_registry
    sys.modules["homeassistant.helpers.selector"] = ha_selector

    sys.modules["voluptuous"] = MagicMock()


_setup_ha_mocks()

from sunny import config_flow as cfg  # noqa: E402


# ---------------------------------------------------------------------------
# Tests _is_window_name_duplicate
# ---------------------------------------------------------------------------

class TestIsWindowNameDuplicate:
    """Régression : la comparaison doit être insensible à la casse et aux
    espaces, sinon « Salon » et « salon » coexistent et les données du
    coordinator s'écrasent mutuellement."""

    def test_exact_duplicate(self):
        windows = [{"name": "salon"}, {"name": "cuisine"}]
        assert cfg._is_window_name_duplicate(windows, "salon") is True

    def test_case_insensitive(self):
        windows = [{"name": "Salon"}]
        assert cfg._is_window_name_duplicate(windows, "salon") is True

    def test_whitespace_insensitive(self):
        windows = [{"name": "salon"}]
        assert cfg._is_window_name_duplicate(windows, " salon ") is True

    def test_case_and_whitespace(self):
        windows = [{"name": "Grand Salon"}]
        assert cfg._is_window_name_duplicate(windows, "GRAND salon ") is True

    def test_different_names(self):
        windows = [{"name": "salon"}]
        assert cfg._is_window_name_duplicate(windows, "cuisine") is False

    def test_exclude_idx(self):
        windows = [{"name": "salon"}, {"name": "cuisine"}]
        assert cfg._is_window_name_duplicate(windows, "salon", exclude_idx=0) is False
        assert cfg._is_window_name_duplicate(windows, "salon", exclude_idx=1) is True

    def test_empty_windows(self):
        assert cfg._is_window_name_duplicate([], "salon") is False
