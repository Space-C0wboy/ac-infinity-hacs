from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DEVICE_MODEL, DOMAIN, MANUFACTURER
from .coordinator import (ACInfinityDataUpdateCoordinator,
                          ActiveBluetoothCoordinatorEntity)
from .device import (WORK_TYPE_AUTO, WORK_TYPE_CYCLE, WORK_TYPE_OFF,
                     WORK_TYPE_ON, WORK_TYPE_TIMER_TO_OFF,
                     WORK_TYPE_TIMER_TO_ON, ACInfinityDevice)
from .models import ACInfinityData

# Display label -> protocol work_type value. This is the full operating mode,
# including On/Off, as a standalone dropdown (complements the fan card, which
# exposes the same modes as power toggle + presets; both stay in sync).
MODE_OPTIONS: dict[str, int] = {
    "Off": WORK_TYPE_OFF,
    "On": WORK_TYPE_ON,
    "Auto": WORK_TYPE_AUTO,
    "Timer to On": WORK_TYPE_TIMER_TO_ON,
    "Timer to Off": WORK_TYPE_TIMER_TO_OFF,
    "Cycle": WORK_TYPE_CYCLE,
}
VALUE_TO_OPTION: dict[int, str] = {v: k for k, v in MODE_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ACInfinityData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ACInfinityModeSelect(data.coordinator, data.device, "Mode")])


class ACInfinityModeSelect(
    ActiveBluetoothCoordinatorEntity[ACInfinityDataUpdateCoordinator], SelectEntity
):
    _attr_has_entity_name = True
    _attr_options = list(MODE_OPTIONS.keys())

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityDevice,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_name = name
        self._attr_unique_id = f"{self._device.address}_select_{slugify(name)}"
        self._attr_device_info = DeviceInfo(
            name=device.name,
            model=DEVICE_MODEL[device.state.type],
            manufacturer=MANUFACTURER,
            sw_version=device.state.version,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )

    async def async_select_option(self, option: str) -> None:
        await self._device.async_set_mode(MODE_OPTIONS[option])

    @callback
    def _update_attrs(self) -> None:
        self._attr_current_option = VALUE_TO_OPTION.get(self._device.state.work_type)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()
