# sensor.py
"""Sensor platform for Milesight WS523."""
from dataclasses import dataclass
from typing import Optional, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    CONF_DEVICE_EUI,
)

@dataclass
class WS523SensorEntityDescription(SensorEntityDescription):
    """Class describing WS523 sensor entities."""
    state_class: str = SensorStateClass.MEASUREMENT
    value_key: str = None


SENSOR_TYPES: tuple[WS523SensorEntityDescription, ...] = (
    WS523SensorEntityDescription(
        key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        value_key="voltage",
    ),
    WS523SensorEntityDescription(
        key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        value_key="current",
    ),
    WS523SensorEntityDescription(
        key="active_power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value_key="active_power",
    ),
    WS523SensorEntityDescription(
        key="power_consumption",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_key="power_consumption",
    ),
    WS523SensorEntityDescription(
        key="power_factor",
        name="Power Factor",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value_key="power_factor",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WS523 sensors."""
    device_eui = config_entry.data[CONF_DEVICE_EUI]
    
    # Store sensor entities in hass.data for access from switch component
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "sensors" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["sensors"] = {}
    
    entities = []
    for description in SENSOR_TYPES:
        sensor = WS523Sensor(device_eui, description)
        entities.append(sensor)
        # Store reference to sensor entity
        if device_eui not in hass.data[DOMAIN]["sensors"]:
            hass.data[DOMAIN]["sensors"][device_eui] = {}
        hass.data[DOMAIN]["sensors"][device_eui][description.value_key] = sensor
    
    async_add_entities(entities)


class WS523Sensor(SensorEntity):
    """Representation of a WS523 Sensor."""

    entity_description: WS523SensorEntityDescription

    def __init__(
            self, device_eui: str, description: WS523SensorEntityDescription
        ) -> None:
            """Initialize the sensor."""
            self.entity_description = description
            self._attr_unique_id = f"{device_eui}_{description.key}"
            self._attr_has_entity_name = True
            self._attr_name = description.name
            self.entity_id = f"sensor.ws523_{device_eui}_{description.key}"
            self._attr_native_value = None
            self._device_eui = device_eui
            
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_eui)},
                name=f"WS523 Smart Plug {device_eui[-4:]}",
                manufacturer="Milesight",
                model="WS523",
            )

    @callback
    def update_from_data(self, value: StateType) -> None:
        """Update the sensor from data."""
        self._attr_native_value = value
        self.async_write_ha_state()