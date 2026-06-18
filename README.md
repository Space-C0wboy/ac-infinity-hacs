[![HACS Custom][hacs_shield]][hacs]
[![Version][version_shield]][commits]
[![License][license_shield]][license]
[![Last commit][lastcommit_shield]][commits]
[![Stars][stars_shield]][stars]
[![Issues][issues_shield]][issues]

[hacs_shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white
[hacs]: https://hacs.xyz/
[version_shield]: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FSpace-C0wboy%2Fac-infinity-hacs%2Fmain%2Fcustom_components%2Fac_infinity%2Fmanifest.json&query=%24.version&label=version&style=for-the-badge&color=0b84f3
[license_shield]: https://img.shields.io/github/license/Space-C0wboy/ac-infinity-hacs?style=for-the-badge
[license]: https://github.com/Space-C0wboy/ac-infinity-hacs/blob/main/LICENSE
[lastcommit_shield]: https://img.shields.io/github/last-commit/Space-C0wboy/ac-infinity-hacs?style=for-the-badge
[commits]: https://github.com/Space-C0wboy/ac-infinity-hacs/commits/main
[stars_shield]: https://img.shields.io/github/stars/Space-C0wboy/ac-infinity-hacs?style=for-the-badge
[stars]: https://github.com/Space-C0wboy/ac-infinity-hacs/stargazers
[issues_shield]: https://img.shields.io/github/issues/Space-C0wboy/ac-infinity-hacs?style=for-the-badge
[issues]: https://github.com/Space-C0wboy/ac-infinity-hacs/issues

# AC Infinity Airtap — Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for **local Bluetooth&nbsp;LE control** of [AC&nbsp;Infinity AIRTAP](https://acinfinity.com/register-booster-fans/) series smart register booster fans. **No cloud, no account, no internet** — Home Assistant talks to the fan directly over Bluetooth.

> **Fork note.** This builds on [mtsphere/ac-infinity-airtap-hacs](https://github.com/mtsphere/ac-infinity-airtap-hacs) (which itself extends [hunterjm/ac-infinity-hacs](https://github.com/hunterjm/ac-infinity-hacs)). Added here: an **operating-mode selector**, a **manual fan-speed control**, a **loggable fan-speed sensor**, and a fix for the discovery config-flow crash. See [Changes in this fork](#changes-in-this-fork).

---

## Table of contents

- [Features](#features)
- [Supported devices](#supported-devices)
- [Requirements](#requirements)
- [Bluetooth range — please read](#bluetooth-range--please-read)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Example automation](#example-automation)
- [Troubleshooting](#troubleshooting)
- [Changes in this fork](#changes-in-this-fork)
- [Credits](#credits)
- [Disclaimer](#disclaimer)

## Features

- 🛜 **100% local** control over Bluetooth LE — works with no internet connection.
- 🔍 **Zero-config auto-discovery** — the fan appears in Home Assistant automatically once it's in Bluetooth range.
- 🌬️ Full fan control: **on/off, speed (1–10), and operating mode** (Off / On / Auto / Timer / Cycle).
- 🌡️ **Onboard temperature sensor** and **Auto-mode temperature triggers** (the fan's built-in thermostat).
- 📈 A read-only **fan-speed sensor** with long-term statistics, so you can graph and log the actual speed over time.
- 📡 Works great through **ESP32 Bluetooth proxies** — essential for fans installed inside metal ductwork (see below).

## Supported devices

| Device | Notes |
| --- | --- |
| **AC Infinity AIRTAP T-series** (T4 / T6 / T8 / T10 …) | Primary target of this fork. Reports BLE device type `6` (“Airtap Series”). |
| UIS Controller **67 / 69 / 69 Pro** | Inherited from the upstream `ac-infinity-ble` library; may work, but the extra entities here are tuned for the AIRTAP. |

Got a model that's detected but missing/odd entities? Please [open an issue][issues] with the model and firmware version.

## Requirements

- Home Assistant with the [**Bluetooth** integration](https://www.home-assistant.io/integrations/bluetooth/) enabled.
- A Bluetooth radio **within range of the fan** — in practice, an [**ESP32 Bluetooth proxy**](https://esphome.io/components/bluetooth_proxy/). Read the next section before you start.
- [HACS](https://hacs.xyz/) (recommended) or manual file install.

## Bluetooth range — please read

> ⚠️ **This is the single most important thing for a reliable setup.**

AIRTAP fans are installed **inside metal register vents and ductwork**, which heavily attenuate Bluetooth. Your Home Assistant host's built-in Bluetooth — or an adapter in another room — will usually **see the fan's advertisements but fail to actually connect to it**, which shows up as *"cannot connect"* during setup or entities that keep going unavailable.

**The robust fix** is a cheap **ESP32 flashed with [ESPHome's Bluetooth Proxy](https://esphome.github.io/bluetooth-proxies/)** placed **right at the vent grille**, with line-of-sight to the opening where the signal escapes:

- Flash any ESP32 from the browser at <https://esphome.github.io/bluetooth-proxies/> (no coding required), join it to Wi-Fi, and Home Assistant will adopt it automatically.
- Position it at the grille face. Aim for an **RSSI better than about −70 dBm** to the fan — advertisements come through at weaker signal, but **connecting and polling needs a stronger link**.
- An ESP32 with an **external antenna** punches through ductwork far better than a bare PCB-antenna board.

## Installation

### HACS (recommended)

1. In Home Assistant, go to **HACS → ⋮ (top right) → Custom repositories**.
2. Add `https://github.com/Space-C0wboy/ac-infinity-hacs` with category **Integration**.
3. Search for **AC Infinity Airtap**, **Download** it, then **restart Home Assistant**.

### Manual

Copy the `custom_components/ac_infinity` folder from this repository into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## Configuration

There is **no YAML configuration**. Once the integration is installed and the fan is within Bluetooth range (via a proxy):

1. Go to **Settings → Devices & Services**.
2. You should see a **Discovered → AC Infinity Airtap** card. Click **Add → Submit**.
   - If setup says *"cannot connect,"* the signal is too weak — move the proxy closer to the grille and **Submit** again (BLE-over-proxy sometimes needs a couple of tries).
3. The device and its entities are created automatically.

> Prefer the **auto-discovery "Add"** prompt over a fully manual *"+ Add Integration"* — discovery uses the safe Bluetooth setup path.

## Entities

For an AIRTAP, the integration creates:

| Entity | Domain | Description |
| --- | --- | --- |
| **Fan** | `fan` | On/off (manual), speed 1–10 (as %), and **preset modes** — **Auto / Timer to On / Timer to Off / Cycle**. |
| **Mode** | `select` | Standalone dropdown for the full operating mode — **Off / On / Auto / Timer to On / Timer to Off / Cycle**. Mirrors the fan's power + presets; both stay in sync. |
| **Fan Speed** | `number` | Manually set the running speed (0–10). Setting it turns the fan on at that speed. |
| **Fan Speed** | `sensor` | Read-only live running speed (0–10) with `measurement` state class — for history/graphs. |
| **Temperature** | `sensor` | The fan's onboard temperature reading. |
| **Min Speed** / **Max Speed** | `number` | Low/high speed bounds used by **Auto** mode. |
| **Auto Mode High/Low Temperature** | `number` | Temperature thresholds for the Auto-mode thermostat. |
| **Auto Mode High/Low Temperature Trigger** | `switch` | Enable/disable each Auto temperature trigger. |

> The device's true state is `mode` + `speed`; the fan entity is a friendly wrapper over it. **Off** = the device's Off mode; **on** = any running mode (On/Auto/Timer/Cycle), with the percentage showing the live speed. The operating mode isn't in the fan's Bluetooth advertisements, so the fan's **preset** may be blank for the first ~30 s after a restart until the first poll completes; it updates instantly thereafter.

## Example automation

Boost the fan when a nearby temperature sensor gets warm, and ease off when it cools:

```yaml
automation:
  - alias: "AIRTAP boost when warm"
    trigger:
      - platform: numeric_state
        entity_id: sensor.living_room_temperature
        above: 78
    action:
      - service: fan.turn_on
        target:
          entity_id: fan.d_6l1x2_fan
        data:
          percentage: 100

  - alias: "AIRTAP off when cool"
    trigger:
      - platform: numeric_state
        entity_id: sensor.living_room_temperature
        below: 74
    action:
      - service: fan.turn_off
        target:
          entity_id: fan.d_6l1x2_fan
```

*(Replace the entity IDs with your own.)* To switch into an automatic mode instead, use `fan.set_preset_mode` with one of `Auto`, `Timer to On`, `Timer to Off`, or `Cycle`.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| **"Config flow could not be loaded: 500 Internal Server Error"** | The upstream config flow crashed (`KeyError: 2306`) when *any* other BLE device was present on a manual add. **Fixed in this fork** — update to the latest. |
| **"Cannot connect" during setup, or entities go unavailable** | Bluetooth signal too weak. Move an **ESP32 Bluetooth proxy** to the vent grille; retry. See [Bluetooth range](#bluetooth-range--please-read). |
| **Mode shows `unknown` after a restart** | Expected briefly — the mode isn't broadcast in advertisements; it fills in after the first poll (~30 s). |
| **No humidity / VPD entities** | AIRTAP T-series are temperature-only; those entities only appear for sensor-equipped controllers. |

To capture debug logs, add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    ac_infinity_ble: debug
    custom_components.ac_infinity: debug
```

## Changes in this fork

- **Operating modes, two synced ways** — as the fan entity's **preset modes** (Auto / Timer to On / Timer to Off / Cycle, with On/Off as the power toggle) **and** a standalone **`select` — Mode** dropdown (full Off / On / Auto / Timer / Cycle). Use whichever you like; they reflect the same state.
- **`number` — manual Fan Speed** (0–10) that sets the running speed and reads the live value.
- **`sensor` — Fan Speed** (read-only, `measurement` state class) for logging and statistics.
- **Config-flow fix**: skip non-AC-Infinity BLE devices during discovery so manual *"Add Integration"* no longer 500s.
- The fan toggle mirrors the operating mode (off only in Off mode) and reflects mode changes immediately instead of waiting for the next poll.

## Credits

- [**mtsphere/ac-infinity-airtap-hacs**](https://github.com/mtsphere/ac-infinity-airtap-hacs) — the AIRTAP-specific integration this fork is based on.
- [**hunterjm/ac-infinity-hacs**](https://github.com/hunterjm/ac-infinity-hacs) and the [**`ac-infinity-ble`**](https://github.com/hunterjm/ac-infinity-ble) library — the original BLE integration and reverse-engineered protocol.
- [**dalinicus/homeassistant-acinfinity**](https://github.com/dalinicus/homeassistant-acinfinity) — a cloud/Wi-Fi AC Infinity integration for UIS controllers.

## Disclaimer

This project is **not affiliated with, authorized, or endorsed by AC Infinity Inc.** "AC Infinity" and "AIRTAP" are trademarks of their respective owner and are used here only to describe device compatibility. Use at your own risk.

## License

Released under the terms in [LICENSE](LICENSE).
