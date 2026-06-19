from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_coordinator import \
    PassiveBluetoothCoordinatorEntity
from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorStateClass)
from collections.abc import Callable
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (PERCENTAGE, EntityCategory, UnitOfPressure,
                                 UnitOfTemperature, UnitOfTime)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DEVICE_MODEL, DOMAIN, FAMILY_E_MODELS, MANUFACTURER
from .coordinator import ACInfinityDataUpdateCoordinator
from .device import ACInfinityDevice
from .models import ACInfinityData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ACInfinityData = hass.data[DOMAIN][entry.entry_id]
    entities = [
        TemperatureSensor(data.coordinator, data.device, "Temperature"),
        FanSpeedSensor(data.coordinator, data.device, "Fan Speed"),
        GenericSensor(data.coordinator, data.device, "Time Remaining",
                      lambda d: d.state.time_remaining,
                      unit=UnitOfTime.MINUTES, icon="mdi:timer-sand"),
    ]

    if data.device.state.type not in [6]:  # Airtap does not have humidity
        entities.append(HumiditySensor(data.coordinator, data.device, "Humidity"))

    if data.device.state.version >= 3 and data.device.state.type in FAMILY_E_MODELS:
        entities.append(VpdSensor(data.coordinator, data.device, "VPD"))
    async_add_entities(entities)


class ACInfinitySensor(
    PassiveBluetoothCoordinatorEntity[ACInfinityDataUpdateCoordinator], SensorEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityDevice,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_name = name
        self._attr_unique_id = f"{self._device.address}_{slugify(name)}"
        self._attr_device_info = DeviceInfo(
            name=device.name,
            model=DEVICE_MODEL[device.state.type],
            manufacturer=MANUFACTURER,
            sw_version=str(device.state.version),
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        raise NotImplementedError("Not yet implemented.")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()


class TemperatureSensor(ACInfinitySensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._device.temperature


class HumiditySensor(ACInfinitySensor):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._device.humidity


class VpdSensor(ACInfinitySensor):
    _attr_native_unit_of_measurement = UnitOfPressure.KPA
    _attr_device_class = SensorDeviceClass.ATMOSPHERIC_PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._device.vpd


class FanSpeedSensor(ACInfinitySensor):
    """Read-only, loggable current fan speed (0-10) from BLE advertisements."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._device.speed


class GenericSensor(ACInfinitySensor):
    """A read-only sensor backed by a getter callable."""

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityDevice,
        name: str,
        get_value: Callable[[ACInfinityDevice], Optional[float]],
        unit: Optional[str] = None,
        device_class: Optional[SensorDeviceClass] = None,
        state_class: Optional[SensorStateClass] = None,
        entity_category: Optional[EntityCategory] = None,
        icon: Optional[str] = None,
    ) -> None:
        self._get_value = get_value
        super().__init__(coordinator, device, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._attr_icon = icon

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._get_value(self._device)
