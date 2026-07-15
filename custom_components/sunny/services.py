"""Services pour l'intégration Sunny."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_AUTO_CONTROL = "set_auto_control"

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


async def _handle_set_auto_control(hass: HomeAssistant, call: ServiceCall) -> None:
    enabled: bool = call.data["enabled"]
    entity_ids = set(call.data.get("entity_id", []))
    area_ids = call.data.get("area_id", [])

    if area_ids:
        ent_reg = er.async_get(hass)
        for area_id in area_ids:
            for entry in er.async_entries_for_area(ent_reg, area_id):
                if entry.domain == "switch" and entry.platform == DOMAIN:
                    entity_ids.add(entry.entity_id)

    if not entity_ids:
        entity_ids = _find_all_auto_control_switches(hass)

    if not entity_ids:
        _LOGGER.warning("Aucun switch de pilotage auto Sunny trouvé")
        return

    service = "turn_on" if enabled else "turn_off"
    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": list(entity_ids)},
        blocking=True,
        context=call.context,
    )


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_AUTO_CONTROL):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AUTO_CONTROL,
        _handle_set_auto_control,
        schema=SCHEMA,
    )