"""Services pour l'intégration Sunny."""

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar, config_validation as cv, entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_AUTO_CONTROL = "set_auto_control"
SERVICE_REFRESH = "refresh"

REFRESH_SCHEMA = vol.Schema({})

SCHEMA = vol.Schema(
    {
        vol.Required("enabled"): cv.boolean,
        vol.Optional("entity_id"): cv.entity_ids,
        vol.Optional("area_id"): [cv.string],
    }
)


def _find_all_auto_control_switches(hass: HomeAssistant) -> set[str]:
    ent_reg = er.async_get(hass)
    entity_ids = set()
    for entry in ent_reg.entities.values():
        if entry.domain == "switch" and entry.platform == DOMAIN:
            entity_ids.add(entry.entity_id)
    return entity_ids


def _filter_sunny_switches(hass: HomeAssistant, entity_ids: set[str]) -> set[str]:
    """Filtre les entity_id fournis : ne garde que les switches Sunny.

    Les cibles inconnues ou étrangères sont ignorées avec un warning au
    lieu de disparaître en silence dans `switch.turn_on`.
    """
    ent_reg = er.async_get(hass)
    resolved: set[str] = set()
    for entity_id in sorted(entity_ids):
        entry = ent_reg.async_get(entity_id)
        if entry is None:
            _LOGGER.warning(
                "set_auto_control : entité '%s' introuvable dans le registre, ignorée",
                entity_id,
            )
            continue
        if entry.domain != "switch" or entry.platform != DOMAIN:
            _LOGGER.warning(
                "set_auto_control : '%s' n'est pas un switch Sunny, ignorée",
                entity_id,
            )
            continue
        resolved.add(entry.entity_id)
    return resolved


def _resolve_area_ids(hass: HomeAssistant, raw_ids: list[str]) -> list[str]:
    area_reg = ar.async_get(hass)
    resolved: list[str] = []
    for value in raw_ids:
        if area_reg.async_get_area(value):
            resolved.append(value)
        elif (area := area_reg.async_get_area_by_name(value)):
            resolved.append(area.id)
    return resolved


async def _handle_set_auto_control(hass: HomeAssistant, call: ServiceCall) -> None:
    enabled: bool = call.data["enabled"]
    raw_entity_ids = set(call.data.get("entity_id", []))
    area_ids = _resolve_area_ids(hass, call.data.get("area_id", []))

    entity_ids: set[str] = set()
    if raw_entity_ids:
        entity_ids = _filter_sunny_switches(hass, raw_entity_ids)

    if area_ids:
        ent_reg = er.async_get(hass)
        for area_id in area_ids:
            for entry in er.async_entries_for_area(ent_reg, area_id):
                if entry.domain == "switch" and entry.platform == DOMAIN:
                    entity_ids.add(entry.entity_id)

    if not entity_ids and not raw_entity_ids:
        entity_ids = _find_all_auto_control_switches(hass)

    if not entity_ids:
        _LOGGER.warning(
            "Aucun switch de pilotage auto Sunny valide trouvé%s",
            " (cibles fournies ignorées)" if raw_entity_ids else "",
        )
        return

    _LOGGER.info(
        "set_auto_control enabled=%s : %d switch(s) → %s",
        enabled, len(entity_ids), ", ".join(sorted(entity_ids)),
    )

    service = "turn_on" if enabled else "turn_off"
    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": list(entity_ids)},
        context=call.context,
    )


async def _handle_refresh(call: ServiceCall) -> None:
    hass = call.hass
    coordinators = list(hass.data.get(DOMAIN, {}).values())
    if not coordinators:
        _LOGGER.warning("Aucune entry Sunny chargée, refresh ignoré")
        return
    await asyncio.gather(*(co.async_refresh() for co in coordinators))


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_AUTO_CONTROL):
        return

    async def _handle(call: ServiceCall) -> None:
        await _handle_set_auto_control(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AUTO_CONTROL,
        _handle,
        schema=SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _handle_refresh,
        schema=REFRESH_SCHEMA,
    )