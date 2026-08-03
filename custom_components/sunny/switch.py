"""Plateforme switch pour l'intégration Sunny."""

import asyncio
import logging
import time

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_COMMAND_TIMEOUT, DEFAULT_POSITION_THRESHOLD, DOMAIN
from .coordinator import SunnyCoordinator
from .sensor import fallback_device_info, resolve_cover_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SunnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    windows = entry.options.get("windows", [])

    entities = []
    for idx, win in enumerate(windows):
        name = win["name"]
        cover_entity_id = win.get("cover_entity", "")
        window_id = win.get("id", win.get("cover_entity", str(idx)))

        if cover_entity_id:
            device_info = await resolve_cover_device(
                hass, entry, cover_entity_id, name
            ) or fallback_device_info(entry, name)
        else:
            device_info = fallback_device_info(entry, name)

        entities.append(
            SunnyAutoControlSwitch(
                coordinator, name, idx, window_id, cover_entity_id, device_info
            )
        )

    async_add_entities(entities)


class SunnyAutoControlSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Switch pour activer/désactiver le pilotage automatique d'un store."""

    _attr_icon = "mdi:auto-fix"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunnyCoordinator,
        window_name: str,
        window_idx: int,
        window_id: str,
        cover_entity_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._window_name = window_name
        self._window_idx = window_idx
        self._cover_entity_id = cover_entity_id
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{window_id}_{window_name}_auto_control"
        )
        self._attr_device_info = device_info
        self._attr_name = f"{window_name} Pilotage auto"
        self._attr_is_on = False
        self._command_target: int | None = None
        self._command_threshold: int = DEFAULT_POSITION_THRESHOLD
        self._command_expires_at: float = 0

    def _set_command_target(self, position: int, threshold: int) -> None:
        """Enregistre la cible suivie par le pilotage auto avec une échéance."""
        self._command_target = position
        self._command_threshold = threshold
        self._command_expires_at = time.monotonic() + float(
            self.coordinator.entry.options.get(
                "command_timeout", DEFAULT_COMMAND_TIMEOUT
            )
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._cover_entity_id], self._on_cover_state_change
            )
        )
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return

        if self._attr_is_on:
            desired_position = data.get("desired_position")
            cover_entity = data.get("cover_entity")
            if desired_position is not None and cover_entity:
                threshold = int(self.coordinator.entry.options.get(
                    "position_threshold", DEFAULT_POSITION_THRESHOLD
                ))
                if self._command_target is not None:
                    if self._expired():
                        if self._command_was_overridden(
                            desired_position, threshold, cover_entity
                        ):
                            self._disable_auto()
                            self.async_write_ha_state()
                            return
                        self._command_target = None
                        self._command_expires_at = 0
                    else:
                        self.async_write_ha_state()
                        return
                if self._should_apply(desired_position, threshold, cover_entity):
                    self._set_command_target(desired_position, threshold)
                    self.hass.async_create_task(
                        self._apply_staggered(cover_entity, desired_position)
                    )

        self.async_write_ha_state()

    @callback
    def _on_cover_state_change(self, event) -> None:
        if not self._attr_is_on:
            return

        new_state = event.data.get("new_state")
        if new_state is None:
            return
        new_position = self._resolve_position(new_state)
        if new_position is None:
            return

        # Suppression des événements pendant que le cover rejoint la cible auto,
        # sauf en cas d'intervention manuelle.
        if self._command_target is not None:
            if abs(new_position - self._command_target) <= self._command_threshold:
                self._command_target = None
                self._command_expires_at = 0
                return
            old_state = event.data.get("old_state")
            if not self._manual_intervention(old_state, new_state, new_position):
                return
            self._command_target = None
            self._command_expires_at = 0

        data = self.coordinator.data.get(self._window_name)
        if data is None:
            return
        desired = data.get("desired_position")
        if desired is not None:
            threshold = int(self.coordinator.entry.options.get(
                "position_threshold", DEFAULT_POSITION_THRESHOLD
            ))
            if not self._position_differs(new_position, desired, threshold):
                return

        self._disable_auto()
        self.async_write_ha_state()

    async def _apply_staggered(self, cover_entity: str, position: int) -> None:
        delay = self._window_idx * self.coordinator.stagger_delay
        if delay > 0:
            await asyncio.sleep(delay)
        await self._apply_position(cover_entity, position)

    async def _apply_position(self, cover_entity: str, position: int) -> None:
        try:
            await self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": cover_entity, "position": position},
                blocking=True,
            )
        except Exception:
            _LOGGER.exception(
                "Erreur lors de l'application de la position %s sur %s",
                position,
                cover_entity,
            )

    def _should_apply(self, new: int, threshold: int, cover_entity: str) -> bool:
        state = self.hass.states.get(cover_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return True
        current = self._resolve_position(state)
        if current is None:
            return True
        if new == current:
            return False
        if new in (0, 100):
            return True
        return abs(new - current) >= threshold

    @staticmethod
    def _resolve_position(state) -> int | None:
        pos = state.attributes.get("current_position")
        if pos is not None:
            try:
                return int(float(pos))
            except (ValueError, TypeError):
                pass
        try:
            return int(float(state.state))
        except (ValueError, TypeError):
            return None

    def _expired(self) -> bool:
        """True si la commande auto en cours a dépassé son échéance."""
        return bool(self._command_expires_at) and time.monotonic() > self._command_expires_at

    def _command_was_overridden(
        self, desired_position: int, threshold: int, cover_entity: str
    ) -> bool:
        """True si, après expiration, le cover n'est pas à la position désirée."""
        state = self.hass.states.get(cover_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return False
        current = self._resolve_position(state)
        if current is None:
            return False
        return self._position_differs(current, desired_position, threshold)

    @staticmethod
    def _position_differs(current: int, desired: int, threshold: int) -> bool:
        """True si la position actuelle diffère vraiment de la position désirée."""
        if abs(current - desired) <= threshold:
            return False
        if desired in (0, 100) and current == desired:
            return False
        return True

    def _manual_intervention(self, old_state, new_state, new_position: int) -> bool:
        """True si le mouvement du cover ne vient pas du pilotage auto.

        Signaux : éloignement de la cible, commande expirée, ou arrivée à
        l'arrêt sur une position différente de la cible.
        """
        target = self._command_target
        tolerance = self._command_threshold
        if self._expired():
            return True
        old_position = self._resolve_position(old_state) if old_state is not None else None
        if old_position is None:
            return False
        if abs(new_position - target) > abs(old_position - target) + tolerance:
            return True
        if (
            self._is_settle_transition(old_state, new_state)
            and abs(new_position - target) > tolerance
        ):
            return True
        return False

    @staticmethod
    def _is_settle_transition(old_state, new_state) -> bool:
        """True si le cover passe d'un état en mouvement à un état à l'arrêt."""
        moving = {"opening", "closing", "moving"}
        stationary = {"open", "closed", "idle", "stopped"}
        if old_state is None or new_state is None:
            return False
        return str(old_state.state) in moving and str(new_state.state) in stationary

    def _disable_auto(self) -> None:
        """Désactive le pilotage auto après une intervention manuelle."""
        self._attr_is_on = False
        self._command_target = None
        self._command_expires_at = 0
        _LOGGER.info(
            "Pilotage auto désactivé pour %s (intervention manuelle détectée)",
            self._window_name,
        )

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        data = self.coordinator.data.get(self._window_name)
        if data:
            desired_position = data.get("desired_position")
            cover_entity = data.get("cover_entity")
            if desired_position is not None and cover_entity:
                threshold = int(self.coordinator.entry.options.get(
                    "position_threshold", DEFAULT_POSITION_THRESHOLD
                ))
                if self._should_apply(desired_position, threshold, cover_entity):
                    self._set_command_target(desired_position, threshold)
                    await self._apply_staggered(cover_entity, desired_position)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self._command_target = None
        self._command_expires_at = 0
        self.async_write_ha_state()
