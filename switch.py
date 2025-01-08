"""Support for Milesight WS523 LoRaWAN smart plug."""
import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional
import functools
import random

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    Platform,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_DEVICE_EUI,
    CONF_QOS,
    DEFAULT_QOS,
    ATTR_CURRENT,
    ATTR_POWER,
    ATTR_ENERGY,
    ATTR_POWER_FACTOR,
    ATTR_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)

# Constants for exponential backoff
INITIAL_BACKOFF = 5  # Initial backoff in seconds
MAX_BACKOFF = 300   # Maximum backoff in seconds (5 minutes)
MAX_RETRIES = None  # None means infinite retries

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WS523 switch from config entry."""
    device_eui = config_entry.data[CONF_DEVICE_EUI]
    qos = config_entry.data.get(CONF_QOS, DEFAULT_QOS)

    device = WS523Device(hass, device_eui, qos)
    async_add_entities([device])

class WS523Device(SwitchEntity, RestoreEntity):
    """Representation of a WS523 smart plug."""

    def __init__(self, hass: HomeAssistant, device_eui: str, qos: int = DEFAULT_QOS) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._device_eui = device_eui
        self._qos = qos
        self._attr_unique_id = f"{DOMAIN}_{device_eui}"
        self._attr_name = f"WS523 Smart Plug {device_eui[-4:]}"
        self._state = None
        self._available = False
        self._retry_count = 0
        self._retry_task = None
        self._attributes = {
            ATTR_VOLTAGE: None,
            ATTR_CURRENT: None,
            ATTR_POWER: None,
            ATTR_ENERGY: None,
            ATTR_POWER_FACTOR: None,
        }

        self._attr_has_entity_name = True
        self._attr_name = "Switch"
        self.entity_id = f"switch.ws523_{device_eui}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_eui)},
            name=f"WS523 Smart Plug {device_eui[-4:]}",
            manufacturer="Milesight",
            model="WS523",
            sw_version="1.0",
        )

    def _calculate_backoff(self) -> float:
        """Calculate the exponential backoff time with jitter."""
        backoff = min(INITIAL_BACKOFF * (2 ** self._retry_count), MAX_BACKOFF)
        # Add random jitter of ±15%
        jitter = backoff * 0.3 * (random.random() - 0.5)
        return backoff + jitter

    async def _connect_mqtt(self) -> bool:
        """Attempt to connect to MQTT and subscribe to topics."""
        try:
            await mqtt.async_subscribe(
                self.hass,
                f"chirpstack/{self._device_eui}/upChannel",
                self._message_received_callback,
                qos=self._qos,
            )
            # Send initial status query
            command = base64.b64encode(bytes.fromhex("ff28ff")).decode()
            await self._publish_command(command)
            self._available = True
            self._retry_count = 0  # Reset retry count on successful connection
            return True
        except Exception as e:
            _LOGGER.error("Failed to connect to MQTT (attempt %d): %s", self._retry_count + 1, e)
            return False

    async def _retry_connection(self) -> None:
        """Implement exponential backoff retry logic."""
        while MAX_RETRIES is None or self._retry_count < MAX_RETRIES:
            if await self._connect_mqtt():
                _LOGGER.info("Successfully connected to MQTT after %d retries", self._retry_count)
                return

            self._retry_count += 1
            backoff = self._calculate_backoff()
            _LOGGER.info("Retrying MQTT connection in %.1f seconds (attempt %d)", 
                        backoff, self._retry_count + 1)
            await asyncio.sleep(backoff)

        _LOGGER.error("Failed to connect to MQTT after maximum retries")

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass."""
        # Restore previous state using RestoreEntity
        last_state = await self.async_get_last_state()
        if last_state:
            self._state = last_state.state == 'on'
            if last_state.attributes:
                for key in self._attributes:
                    if key in last_state.attributes:
                        self._attributes[key] = last_state.attributes[key]
        
        # Start initial connection attempt
        if not await self._connect_mqtt():
            self._retry_task = asyncio.create_task(self._retry_connection())

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._retry_task is not None:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

    def _message_received_callback(self, msg) -> None:
        """Handle received MQTT message."""
        self.hass.add_job(self._handle_message, msg)

    async def _handle_message(self, msg) -> None:
        """Process the MQTT message in the event loop."""
        try:
            payload = json.loads(msg.payload)
            if not isinstance(payload, dict):
                _LOGGER.error("Invalid message format: not a JSON object")
                return
                
            if "decoded" not in payload or "payload" not in payload["decoded"]:
                _LOGGER.error("Missing decoded payload in message")
                return
                
            data = payload["decoded"]["payload"]
            
            if "socket_status" in data:
                new_state = data["socket_status"] == "open"
                if self._state != new_state:
                    self._state = new_state
                    command = base64.b64encode(bytes.fromhex("ff28ff")).decode()
                    await self._publish_command(command)
            
            for attr_key, data_key in [
                (ATTR_VOLTAGE, "voltage"),
                (ATTR_CURRENT, "current"),
                (ATTR_POWER, "active_power"),
                (ATTR_ENERGY, "power_consumption"),
                (ATTR_POWER_FACTOR, "power_factor"),
            ]:
                if data_key in data:
                    self._attributes[attr_key] = data[data_key]
            
            if (DOMAIN in self.hass.data and 
                "sensors" in self.hass.data[DOMAIN] and 
                self._device_eui in self.hass.data[DOMAIN]["sensors"]):
                sensors = self.hass.data[DOMAIN]["sensors"][self._device_eui]
                for value_key, value in data.items():
                    if value_key in sensors:
                        sensors[value_key].update_from_data(value)
            
            self._available = True
            self.async_write_ha_state()
            
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to decode JSON message: %s", e)
        except Exception as e:
            _LOGGER.error("Error processing message: %s", str(e))

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return self._attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        command = base64.b64encode(bytes.fromhex("080100ff")).decode()
        await self._publish_command(command)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        command = base64.b64encode(bytes.fromhex("080000ff")).decode()
        await self._publish_command(command)

    async def _publish_command(self, command: str) -> None:
        """Publish command to MQTT."""
        try:
            payload = {
                "payload_raw": command,
                "port": 85,
                "confirmed": True
            }
            topic = f"chirpstack/{self._device_eui}/dnChannel"
            await mqtt.async_publish(
                self.hass, 
                topic, 
                json.dumps(payload),
                qos=self._qos
            )
        except Exception as e:
            _LOGGER.error("Failed to publish MQTT command: %s", e)
            self._available = False
            if self._retry_task is None or self._retry_task.done():
                self._retry_task = asyncio.create_task(self._retry_connection())