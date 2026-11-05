"""Proves an AC Infinity advertisement still decodes the same way after an ac-infinity-ble bump."""

from custom_components.ac_infinity.config_flow import parse_manufacturer_data


def advert(dev_type=11, version=3, temp_c=23.5, hum=55.0, fan=4, port=2, vpd=1.25):
    data = bytearray(23)
    data[6:11] = b"T4A1B"  # device id, shown in the name
    data[11] = version
    data[12] = dev_type
    data[13] = 0b00000000  # flags: degrees C, all states 0
    data[14:16] = int(temp_c * 100).to_bytes(2, "big", signed=True)
    data[16:18] = int(hum * 100).to_bytes(2, "big", signed=True)
    data[18] = fan
    data[19] = port
    data[21:23] = int(vpd * 100).to_bytes(2, "big", signed=True)
    return bytes(data)


def test_airtap_advert_decodes():
    d = parse_manufacturer_data(advert())
    assert d.name == "G-T4A1B"
    assert (d.tmp, d.hum, d.fan) == (23.5, 55.0, 4)
    assert (d.choose_port, d.vpd) == (2, 1.25)


def test_negative_temperature():
    assert parse_manufacturer_data(advert(temp_c=-5.0)).tmp == -5.0


def test_old_firmware_has_no_port_or_vpd():
    d = parse_manufacturer_data(advert(version=2))
    assert d.choose_port is None or d.choose_port == 0
