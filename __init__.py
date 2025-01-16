"""The Milesight WS523 integration."""
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_DEVICE_EUI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DEVICE_EUI): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

DEVICE_CARDS = {
    "sensors": {
        "type": "entities",
        "entities": [
            {"entity": "{entity_id_prefix}_voltage"},
            {"entity": "{entity_id_prefix}_current"},
            {"entity": "{entity_id_prefix}_power"},
            {"entity": "{entity_id_prefix}_energy"},
            {"entity": "{entity_id_prefix}_power_factor"}
        ],
        "title": "WS523 Sensors"
    },
    "controls": {
        "type": "entities",
        "entities": [
            {"entity": "{entity_id_prefix}_switch"}
        ],
        "title": "WS523 Controls"
    }
}

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Milesight WS523 component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Milesight WS523 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    
    # Register device cards
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_DEVICE_EUI])},
        manufacturer="Milesight",
        model="WS523",
        name=f"WS523 Smart Plug {entry.data[CONF_DEVICE_EUI][-4:]}"
    )

    # Register the device cards with Home Assistant
    if device:
        entity_prefix = f"{DOMAIN}_{entry.data[CONF_DEVICE_EUI]}"
        
        for card_type, card_config in DEVICE_CARDS.items():
            formatted_entities = []
            for entity in card_config["entities"]:
                entity_id = entity["entity"].format(entity_id_prefix=entity_prefix)
                if entity_registry.async_get(entity_id):
                    formatted_entities.append({"entity": entity_id})
            
            if formatted_entities:
                hass.data[DOMAIN].setdefault("device_cards", {})
                hass.data[DOMAIN]["device_cards"][device.id] = {
                    card_type: {
                        **card_config,
                        "entities": formatted_entities
                    }
                }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok