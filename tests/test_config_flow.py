"""Proves the user setup step lists AC Infinity devices and ignores every other BLE device."""

from types import SimpleNamespace
from unittest.mock import patch

from ac_infinity_ble.const import MANUFACTURER_ID

from custom_components.ac_infinity.config_flow import ConfigFlow

from .test_parse import advert

PATCH = "custom_components.ac_infinity.config_flow.async_discovered_service_info"


def ble(address, manufacturer_data):
    return SimpleNamespace(
        address=address, advertisement=SimpleNamespace(manufacturer_data=manufacturer_data)
    )


async def _user_step(hass, discovered):
    flow = ConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    with patch(PATCH, return_value=discovered):
        return await flow.async_step_user()


async def test_lists_ac_infinity_device(hass):
    result = await _user_step(hass, [ble("AA:BB:CC:DD:EE:01", {MANUFACTURER_ID: advert()})])
    assert result["type"] == "form" and result["step_id"] == "user"
    choices = result["data_schema"].schema["address"].container
    assert choices == {"AA:BB:CC:DD:EE:01": "G-T4A1B (AA:BB:CC:DD:EE:01)"}


async def test_other_ble_devices_are_skipped_not_a_crash(hass):
    # regression: a non-AC Infinity advert used to raise KeyError 2306 ("Config flow could not be loaded: 500")
    result = await _user_step(hass, [ble("11:22:33:44:55:66", {76: b"\x02\x15"})])
    assert result["type"] == "abort" and result["reason"] == "no_devices_found"


async def test_no_devices(hass):
    result = await _user_step(hass, [])
    assert result["type"] == "abort" and result["reason"] == "no_devices_found"
