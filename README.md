# Dragino LoRaWAN for Home Assistant

![Dragino](custom_components/dragino/brand/logo.png)

A [HACS](https://hacs.xyz) custom integration that turns [Dragino](https://www.dragino.com)
LoRaWAN sensors into Home Assistant devices and entities.

Home Assistant's core **LoRaWAN** integration only connects to a network server
(ChirpStack, The Things Stack) and lists the devices it knows about. It does not know what
a Dragino payload means. This integration is the vendor-specific part: it decodes the uplinks
of Dragino devices that your LoRaWAN connection already receives and creates the Home Assistant
devices and entities for them. No MQTT topics or payload decoders have to be configured on the
network server.

```text
Dragino device ──LoRaWAN──▶ ChirpStack / The Things Stack ──▶ core "LoRaWAN" ──▶ Dragino (this integration)
```

## Requirements

- Home Assistant **2026.11** or newer (the core `lorawan` integration is required).
- At least one LoRaWAN connection set up in Home Assistant, for ChirpStack or The Things Stack.
- Your Dragino devices registered on that network server and sending uplinks.

## Installation

1. In HACS, open **⋮ → Custom repositories**, add `https://github.com/tomfrenzel/ha-dragino`
   with the category **Integration**, and download **Dragino LoRaWAN**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services**. Dragino is offered automatically once a LoRaWAN
   connection reports a supported device. Otherwise use **Add integration → Dragino**.
4. Confirm. Supported devices from every LoRaWAN connection are added.

There is a single Dragino entry for all connections. Devices that join later are picked up
automatically.

## Supported devices

| Model | Entities | ChirpStack catalog | The Things Stack repository |
| --- | --- | --- | --- |
| LDDS75 | Distance, temperature | ✅ | `dragino/ldds75` |
| LDS02 | Door, alarm, open count and duration | ✅ | `dragino/lds02` |
| LWL02 | Water leak, alarm, leak count and duration | ✅ | `dragino/lwl02` |
| LHT65N | Temperature, humidity, external probe (temperature, humidity, illuminance, ADC, counter, PIR), interrupt | ✅ | `dragino/lht65n` |
| T68DL | Temperature, high/low threshold alarms | ✅ | not in the repository, matched by name |
| LT-22222-L | 2 digital inputs, 2 digital outputs, 2 relays, 2 × 0–10 V, 2 × 4–20 mA, 2 counters | ✅ | `dragino/lt22222-l` |
| CPL03-LB | Contact status, alarm, pulse count and last duration, or 3 contact states and pulse counts | ✅ | `dragino/cpl03-lb` |

Battery voltage and firmware version sensors appear when the device reports those values.
RSSI/SNR sensors are available but **disabled by default**.

### Entities appear with the first uplink

The entities that every unit of a model always reports (for example temperature and humidity on
an LHT65N) exist as soon as the device is added and show `unknown` until the first uplink.
Entities that depend on the payload, the work mode or the attached probe are created when the
first uplink containing a value arrives. Once created, an entity stays and shows `unknown` if a
later uplink has no value.

## How devices are recognised

1. **Catalog identifiers.** The network server reports which catalog device a device profile
   was created from (ChirpStack vendor 676, or The Things Stack brand `dragino`). Devices that
   match a model above are used directly.
2. **Name fallback.** If the catalog id is not known to this integration, the model name is
   compared with the Dragino model names (case and separators are ignored), but only for the
   Dragino brand.

For ChirpStack, create the device profile from the catalog entry of the Dragino device so the
connection can report the model.

## Downlink controls

Controls use the existing LoRaWAN connection; there is no separate MQTT or server configuration.
The connection's credentials must allow queuing downlinks.

| Devices | Home Assistant control | Purpose |
| --- | --- | --- |
| All supported models | **Requested reporting interval** number | Request an uplink interval in seconds |
| LT-22222-L | **Relay 1/2 control** switches | Open or close each relay |
| LT-22222-L | **Digital output 1/2 control** switches | Activate or release each output |
| LT-22222-L | **Request measurement** button | Request a measurement uplink |
| CPL03-LB, T68DL, LHT65N | **Request device status** button | Request device information |

- Controlling one output leaves the other outputs unchanged. Relay **on** means closed; digital output
  **on** means the NPN output is pulled **low** (active). Off opens the relay or releases the
  digital output (high/floating).
- Switch states come only from received uplinks. A queued command does **not** optimistically
  change them. The original read-only binary sensors remain available for existing automations.
- The interval number records the **last successfully queued request**, not a confirmed device
  setting. It starts as `unknown`, resets to `unknown` after reload, and is never automatically
  resent. It accepts whole seconds from 1 to 16,777,215; choose
  values appropriate for the device firmware, battery life, regional duty-cycle limits and
  your network's fair-use policy.
- Downlinks are queued as **unconfirmed** messages. A successful action means the server
  accepted the request, not that the device received or applied it. Battery-powered Class A
  devices receive downlinks only after an uplink, which may take hours at the existing interval.
  Class C LT-22222-L controllers can receive them sooner. Lost commands are not retried automatically.
- Queue failures are shown as action errors. An enqueue timeout may still have queued the
  command; check the network server before retrying.
- LHT65N status requests require firmware **1.4.0+**. A known older version is rejected; when
  the version is unknown, check your firmware before using the button.
- A button's timestamp records the press attempt, not delivery or receipt of a response.

For example, an automation can request a ten-minute reporting interval:

```yaml
action: number.set_value
target:
  entity_id: number.your_device_requested_reporting_interval
data:
  value: 600
```

See the official Dragino manuals for device-specific behavior and firmware requirements:
[LT-22222-L](https://docs.dragino.com/docs/LoRaWAN-End-Node/io-controllers-sensor-nodes/lt-22222-l/),
[CPL03-LB](https://docs.dragino.com/docs/LoRaWAN-End-Node/door-water-leak-contact-sensors/cpl03-lb/),
[LDDS75](https://docs.dragino.com/docs/LoRaWAN-End-Node/distance-level-detection/ldds75/),
[LDS02](https://docs.dragino.com/docs/LoRaWAN-End-Node/door-water-leak-contact-sensors/lds02/),
[LWL02](https://docs.dragino.com/docs/LoRaWAN-End-Node/door-water-leak-contact-sensors/lwl02/),
[LHT65N](https://docs.dragino.com/docs/LoRaWAN-End-Node/temperature-humidity-sensors/lht65n/), and
[T68DL](https://docs.dragino.com/docs/LoRaWAN-End-Node/temperature-humidity-sensors/t68dl/).

## Limitations

- Advanced downlinks (factory reset, keys, work-mode changes and timed output pulses) are
  intentionally not exposed.
- Frames that are not live measurements (for example LHT65N history frames) are ignored.
- Payloads and command bytes are tested against vendor documentation and mock LoRaWAN connections,
  not physical devices. Verify behavior on your hardware before relying on output controls.
- Models not listed in the supported-devices table are not supported.

## Home Assistant compatibility

Automated tests run daily against the latest stable Home Assistant release to detect
compatibility problems. They cannot guarantee compatibility with future releases or every
device firmware version.

## Troubleshooting

### Reporting a problem

[Open an issue](https://github.com/tomfrenzel/ha-dragino/issues) with your Home Assistant version,
network server, Dragino model, firmware version and relevant logs. Remove credentials, keys
and other sensitive information before sharing logs.

## License

The software is [MIT licensed](LICENSE). It includes decoder code adapted from
[`chirpstack-device-profiles`](https://github.com/chirpstack/chirpstack-device-profiles)
and retains that project's MIT copyright notice.

## Disclaimer

The icon and logo are derived from the Dragino mark in
[The Things Network device repository](https://github.com/TheThingsNetwork/lorawan-devices/blob/25a0ab3e7e0bb2f18e7c1c00aef85e04fd6b0af1/vendor/dragino/logo.png).
The mark belongs to Dragino and is used to identify the supported devices.
This project is not affiliated with or endorsed by Dragino.
