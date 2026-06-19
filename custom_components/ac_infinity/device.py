from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from typing import Optional

from ac_infinity_ble import ACInfinityController, DeviceInfo
from ac_infinity_ble.const import CallbackType, MANUFACTURER_ID
from ac_infinity_ble.protocol import parse_manufacturer_data
from ac_infinity_ble.util import get_bit
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .const import FAMILY_E_MODELS

WORK_TYPE_OFF = 1
WORK_TYPE_ON = 2
WORK_TYPE_AUTO = 3
WORK_TYPE_TIMER_TO_ON = 4
WORK_TYPE_TIMER_TO_OFF = 5
WORK_TYPE_CYCLE = 6

# work_type values that are valid operating modes for the device
WORK_TYPES = (
    WORK_TYPE_OFF,
    WORK_TYPE_ON,
    WORK_TYPE_AUTO,
    WORK_TYPE_TIMER_TO_ON,
    WORK_TYPE_TIMER_TO_OFF,
    WORK_TYPE_CYCLE,
)

_LOGGER = logging.getLogger(ACInfinityController.__module__)
# Connecting suppresses the fan's advertisements and ties up a single proxy's
# radio, so poll sparingly (settings change rarely; user changes still trigger
# an immediate poll via _config_changed_since_last_update).
_MIN_SECONDS_BETWEEN_POLLS = 90


@dataclass
class DeviceInfoEx(DeviceInfo):
    @staticmethod
    def create(device_info: DeviceInfo) -> DeviceInfoEx:
        return DeviceInfoEx(**device_info.__dict__)

    auto_mode: Optional[AutoModeConfig] = None
    # Durations in minutes (the wire format is seconds; we store/expose minutes,
    # matching the official app). None until the first poll.
    timer_to_on: Optional[int] = None
    timer_to_off: Optional[int] = None
    cycle_on: Optional[int] = None
    cycle_off: Optional[int] = None
    # Read from an optional secondary poll (params 24/33/35/36). Read-only for
    # now until the on-wire formats are verified against the app.
    time_remaining: Optional[int] = None       # minutes (best-effort decode)
    backlight: Optional[int] = None            # raw brightness gear
    temp_calibration: Optional[int] = None     # degrees C (signed)
    temp_buffer: Optional[int] = None          # degrees C


@dataclass
class AutoModeConfig:
    high_temp_enabled: bool
    high_temp: int
    low_temp_enabled: bool
    low_temp: int
    high_humidity_enabled: bool
    high_humidity: int
    low_humidity_enabled: bool
    low_humidity: int


class ACInfinityDevice(ACInfinityController):
    _config_changed_since_last_update = False

    def __init__(
        self,
        ble_device: BLEDevice,
        state: DeviceInfoEx | None = None,
        advertisement_data: AdvertisementData | None = None,
    ):
        super().__init__(
            ble_device=ble_device,
            state=state,
            advertisement_data=advertisement_data,
        )

        if self._state is DeviceInfo:
            self._state = DeviceInfoEx(**self._state.__dict__)

    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data
        info = parse_manufacturer_data(
            advertisement_data.manufacturer_data[MANUFACTURER_ID]
        )
        self._state = dataclasses.replace(
            self._state, **{k: v for k, v in dataclasses.asdict(info).items() if v is not None}
        )
        self._fire_callbacks(CallbackType.ADVERTISEMENT)

    @property
    def speed(self) -> Optional[int]:
        """Get the speed of the device."""
        return self._state.fan

    @property
    def temperature(self) -> Optional[float]:
        """Get the temperature of the device."""
        return self._state.tmp

    @property
    def humidity(self) -> Optional[float]:
        """Get the humidity of the device."""
        return self._state.hum

    @property
    def vpd(self) -> Optional[float]:
        """Get the vpd of the device."""
        return self._state.vpd

    @property
    def auto_mode(self) -> Optional[AutoModeConfig]:
        return self._state.auto_mode

    @property
    def min_speed(self) -> Optional[int]:
        return self._state.level_off

    @property
    def max_speed(self) -> Optional[int]:
        return self._state.level_on

    @property
    def state(self) -> DeviceInfoEx:
        return self._state

    def update_needed(self, seconds_since_last_update: Optional[float | int]) -> bool:
        return (self._config_changed_since_last_update or
                seconds_since_last_update is None or seconds_since_last_update > _MIN_SECONDS_BETWEEN_POLLS)

    async def update(self) -> None:
        """Poll the device to update state date, including data not present in BLE advertisements."""
        await self._ensure_connected()
        try:
            _LOGGER.debug("%s: Updating model data", self.name)
            command = self._protocol.get_model_data(self.state.type, 0, self.sequence)
            if data := await self._send_command(command):
                if len(data) < 28:
                    _LOGGER.debug(
                        "%s: Skipping update; data too short (%s): %s",
                        self.name,
                        len(data),
                        data.hex()
                    )
                else:
                    self.state.work_type = data[12]
                    self.state.level_off = data[15]
                    self.state.level_on = data[18]

                    self.state.auto_mode = AutoModeConfig(
                        high_temp_enabled=not get_bit(data[21], 4),
                        low_temp_enabled=not get_bit(data[21], 5),
                        high_humidity_enabled=not get_bit(data[21], 6),
                        low_humidity_enabled=not get_bit(data[21], 7),
                        high_temp=data[23],
                        low_temp=data[25],
                        high_humidity=data[26],
                        low_humidity=data[27],
                    )

                    # Walk the response's [param][len][value...] TLVs to read the
                    # timer/cycle durations (params 20/21/22). Values are 4-byte
                    # big-endian seconds; cycle (22) is two such values [on, off].
                    tlvs: dict[int, bytes] = {}
                    plen = (data[2] << 8) | data[3]
                    i = 10
                    end = min(10 + plen, len(data))
                    while i + 1 < end:
                        pid = data[i]
                        ln = data[i + 1]
                        tlvs[pid] = data[i + 2:i + 2 + ln]
                        i += 2 + ln
                    if (v := tlvs.get(20)) and len(v) >= 4:
                        self.state.timer_to_on = int.from_bytes(v[:4], "big") // 60
                    if (v := tlvs.get(21)) and len(v) >= 4:
                        self.state.timer_to_off = int.from_bytes(v[:4], "big") // 60
                    if (v := tlvs.get(22)) and len(v) >= 8:
                        self.state.cycle_on = int.from_bytes(v[:4], "big") // 60
                        self.state.cycle_off = int.from_bytes(v[4:8], "big") // 60

                    self._config_changed_since_last_update = False
                    self._fire_callbacks(CallbackType.UPDATE_RESPONSE)

            # Best-effort secondary read of params not in the standard model
            # response: 24 (time remaining), 33 (backlight), 35 (temp buffer),
            # 36 (temp calibration). Isolated so a failure never breaks the main
            # poll. Formats are decoded from the v1.5.8 source and remain
            # read-only until verified against the official app.
            try:
                extra = [24, 33, 35, 36]
                if self.state.type in FAMILY_E_MODELS:
                    extra = extra + [255, 0]
                cmd = self._protocol._add_head(extra, 1, self.sequence)
                if data2 := await self._send_command(cmd):
                    tl2: dict[int, bytes] = {}
                    plen2 = (data2[2] << 8) | data2[3]
                    j = 10
                    end2 = min(10 + plen2, len(data2))
                    while j + 1 < end2:
                        tl2[data2[j]] = data2[j + 2:j + 2 + data2[j + 1]]
                        j += 2 + data2[j + 1]
                    if (v := tl2.get(24)) and len(v) >= 4:
                        self.state.time_remaining = int.from_bytes(v[:4], "big") // 60
                    if (v := tl2.get(33)) and len(v) >= 1:
                        self.state.backlight = v[0]
                    if (v := tl2.get(35)) and len(v) >= 2:
                        self.state.temp_buffer = v[1]
                    if (v := tl2.get(36)) and len(v) >= 2:
                        self.state.temp_calibration = int.from_bytes(
                            v[1:2], "big", signed=True
                        )
                    self._fire_callbacks(CallbackType.UPDATE_RESPONSE)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "%s: optional extra-params read failed", self.name, exc_info=True
                )
        finally:
            await self._execute_disconnect()

    async def set_mode_auto(self) -> None:
        """Set the device's mode to automatic."""
        await self.async_set_mode(WORK_TYPE_AUTO)

    async def async_set_mode(self, work_type: int) -> None:
        """Set the device's operating mode (work_type)."""
        if work_type not in WORK_TYPES:
            raise ValueError(f"Unsupported work_type: {work_type}")

        _LOGGER.debug("%s: Setting mode to %s", self.name, work_type)

        command = [16, 1, work_type]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)
        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.work_type = work_type
            self._config_changed_since_last_update = True
            # Push the new mode to HA entities immediately rather than waiting
            # for the next poll (work_type is not present in advertisements).
            self._fire_callbacks(CallbackType.UPDATE_RESPONSE)
        finally:
            await self._execute_disconnect()

    async def async_set_auto_high_temp(self, value: float) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, high_temp=round(value))
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_low_temp(self, value: float) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, low_temp=round(value))
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_mode_high_temp_enabled(self, enabled: bool) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, high_temp_enabled=enabled)
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_mode_low_temp_enabled(self, enabled: bool) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, low_temp_enabled=enabled)
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_mode_config(self, config: AutoModeConfig) -> None:
        if config is None:
            raise ValueError("config cannot be None")
        _LOGGER.debug("%s: Setting auto mode config to %s", self.name, config)

        def byte_for_temp_hum_enabled_switches(config: AutoModeConfig) -> int:
            b = 8 if config.high_temp_enabled else 0
            if config.low_temp_enabled:
                b |= 4
            if config.high_humidity_enabled:
                b |= 2
            if config.low_humidity_enabled:
                b |= 1
            return b

        def c_to_f(celsius: float) -> float:
            return round((celsius * 9.0 / 5.0) + 32.0, 2)

        temp_hum_enabled_switches = byte_for_temp_hum_enabled_switches(config)
        # Note: Logic does not differ based on value of is_degree, as that is a display flag only.
        # The protocol has both Celsius and Fahrenheit values; our data model uses Celsius only.
        high_temp_f = round(c_to_f(config.high_temp))
        high_temp_c = config.high_temp
        low_temp_f = round(c_to_f(config.low_temp))
        low_temp_c = config.low_temp

        command = [19, 7,
                   temp_hum_enabled_switches,
                   high_temp_f, high_temp_c,
                   low_temp_f, low_temp_c,
                   config.high_humidity,
                   config.low_humidity]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)

        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.auto_mode = config
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()

    async def async_set_min_speed(self, value: int) -> None:
        """Set the minimum fan speed for auto and other dynamic modes."""
        if value not in range(0, 11):
            raise ValueError("value must be between 0 and 10")

        _LOGGER.debug("%s: Setting min speed to %s", self.name, value)

        command = [17, 1, value]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)

        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.level_off = value
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()

    @staticmethod
    def _minutes_seconds_bytes(minutes: int) -> list[int]:
        """Encode a duration in minutes as the protocol's 4-byte BE seconds."""
        return list(int(max(0, int(minutes)) * 60).to_bytes(4, "big"))

    async def _async_set_duration(self, command: list[int], **new_state) -> None:
        """Send a SET (work command 3) for a [param, len, *value] duration TLV.

        On success, apply ``new_state`` to the device state and notify entities.
        """
        if self.state.type in FAMILY_E_MODELS:
            command = command + [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)
        await self._ensure_connected()
        try:
            await self._send_command(command)
            for key, value in new_state.items():
                setattr(self.state, key, value)
            self._config_changed_since_last_update = True
            self._fire_callbacks(CallbackType.UPDATE_RESPONSE)
        finally:
            await self._execute_disconnect()

    async def async_set_timer_to_on(self, minutes: int) -> None:
        """Set the 'timer to on' duration, in minutes."""
        _LOGGER.debug("%s: Setting timer-to-on to %s min", self.name, minutes)
        await self._async_set_duration(
            [20, 4] + self._minutes_seconds_bytes(minutes), timer_to_on=int(minutes)
        )

    async def async_set_timer_to_off(self, minutes: int) -> None:
        """Set the 'timer to off' duration, in minutes."""
        _LOGGER.debug("%s: Setting timer-to-off to %s min", self.name, minutes)
        await self._async_set_duration(
            [21, 4] + self._minutes_seconds_bytes(minutes), timer_to_off=int(minutes)
        )

    async def async_set_cycle(self, on_minutes: int, off_minutes: int) -> None:
        """Set the cycle on/off durations, in minutes."""
        _LOGGER.debug(
            "%s: Setting cycle to on=%s off=%s min", self.name, on_minutes, off_minutes
        )
        await self._async_set_duration(
            [22, 8]
            + self._minutes_seconds_bytes(on_minutes)
            + self._minutes_seconds_bytes(off_minutes),
            cycle_on=int(on_minutes),
            cycle_off=int(off_minutes),
        )

    async def async_set_cycle_on(self, minutes: int) -> None:
        """Set the cycle 'on' duration (minutes), keeping the current off."""
        await self.async_set_cycle(int(minutes), self.state.cycle_off or 0)

    async def async_set_cycle_off(self, minutes: int) -> None:
        """Set the cycle 'off' duration (minutes), keeping the current on."""
        await self.async_set_cycle(self.state.cycle_on or 0, int(minutes))

    async def async_set_backlight(self, value: int) -> None:
        """Set the display backlight brightness gear."""
        _LOGGER.debug("%s: Setting backlight to %s", self.name, value)
        await self._async_set_duration(
            [33, 1, int(value) & 0xFF], backlight=int(value)
        )

    async def async_set_temp_calibration(self, celsius: int) -> None:
        """Set the temperature calibration offset, in degrees C.

        The wire format carries both a degF and degC byte (the device uses the
        one matching its display unit); this mirrors the official app's encoding.
        """
        c = int(celsius)
        f = round(c * 9 / 5 + 32)
        _LOGGER.debug("%s: Setting temp calibration to %s C", self.name, c)
        await self._async_set_duration(
            [36, 3, f & 0xFF, c & 0xFF, 0], temp_calibration=c
        )

    async def async_set_max_speed(self, value: int) -> None:
        """Set the maximum fan speed for auto and other dynamic modes."""
        if value not in range(0, 11):
            raise ValueError("value must be between 0 and 10")

        _LOGGER.debug("%s: Setting max speed to %s", self.name, value)

        command = [18, 1, value]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)

        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.level_off = value
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()
