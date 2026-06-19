from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from homeassistant.util.percentage import (int_states_in_range,
                                           percentage_to_ranged_value,
                                           ranged_value_to_percentage)

from .const import DEVICE_MODEL, DOMAIN, MANUFACTURER
from .coordinator import (ACInfinityDataUpdateCoordinator,
                          ActiveBluetoothCoordinatorEntity)
from .device import (WORK_TYPE_AUTO, WORK_TYPE_CYCLE, WORK_TYPE_OFF,
                     WORK_TYPE_TIMER_TO_OFF, WORK_TYPE_TIMER_TO_ON,
                     ACInfinityDevice)
from .models import ACInfinityData

SPEED_RANGE = (1, 10)

# Fan presets map onto the device's non-manual operating modes. On/Off are
# represented by the fan's power toggle, so they are not presets.
PRESET_AUTO = "Auto"
PRESET_TIMER_TO_ON = "Timer to On"
PRESET_TIMER_TO_OFF = "Timer to Off"
PRESET_CYCLE = "Cycle"

PRESET_TO_WORK_TYPE = {
    PRESET_AUTO: WORK_TYPE_AUTO,
    PRESET_TIMER_TO_ON: WORK_TYPE_TIMER_TO_ON,
    PRESET_TIMER_TO_OFF: WORK_TYPE_TIMER_TO_OFF,
    PRESET_CYCLE: WORK_TYPE_CYCLE,
}
WORK_TYPE_TO_PRESET = {v: k for k, v in PRESET_TO_WORK_TYPE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ACInfinityData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ACInfinityFan(data.coordinator, data.device, "Fan")])


class ACInfinityFan(
    ActiveBluetoothCoordinatorEntity[ACInfinityDataUpdateCoordinator], FanEntity
):
    _attr_has_entity_name = True
    _attr_speed_count = int_states_in_range(SPEED_RANGE)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = list(PRESET_TO_WORK_TYPE)

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

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        speed = 0
        if percentage > 0:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        await self._device.set_speed(speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        speed = None
        if percentage is not None:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self._device.turn_on(speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.turn_off()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        work_type = PRESET_TO_WORK_TYPE.get(preset_mode)
        if work_type is None:
            raise ValueError(f"Unsupported preset mode: {preset_mode}")
        await self._device.async_set_mode(work_type)

    @callback
    def _update_attrs(self) -> None:
        """Handle updating _attr values."""
        work_type = self._device.state.work_type
        # The device's real state is (mode, speed). Mirror the mode here so the
        # fan toggle never contradicts the Mode select: off only in Off mode, on
        # in any running mode (On/Auto/Timer/Cycle). Before the first poll
        # work_type is unknown, so fall back to whether the fan is actually
        # spinning. The percentage always reflects the live speed.
        if work_type is None:
            self._attr_is_on = bool(self._device.state.fan)
        else:
            self._attr_is_on = work_type != WORK_TYPE_OFF
        self._attr_preset_mode = WORK_TYPE_TO_PRESET.get(work_type)
        self._attr_percentage = ranged_value_to_percentage(
            SPEED_RANGE, self._device.state.fan or 0
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()
