# Solar Charger Binary Modbus Command Overview

## Scope and evidence

This reference describes every command path exercised by the decompiled solar-charger monitor in `.refbin` (the extracted form of the supplied `.rebin`/DLL material). It targets the controller family used by that monitor—not Victron VE.Direct MPPT chargers—and addresses below are **zero-based Modbus protocol addresses**.

**Confidence:** command function codes, addresses, and quantities are confirmed by the client code. Names, value units, and bit interpretation are confirmed where the data model decodes them; anything else is explicitly marked **inferred**. All commands are Modbus RTU requests (`unit-id | PDU | CRC16`, CRC low byte first). The unit ID is caller-selected unless noted. The client uses a 1 s read timeout, 500 ms write timeout, one retry, and waits 20 ms after creating a master.

> **Warning:** Write commands can change charging, load, configuration, device identity, and counters. Test only on non-production hardware and preserve its configuration first.

## Function-code summary

| FC (hex) | Operation | Use in solar-charger client |
|---|---|---|
| `01` | Read coils | Available in transport; no application operation uses it. |
| `02` | Read discrete inputs | Reads over-temperature input `8192`. |
| `03` | Read holding registers | Date/time only. |
| `04` | Read input registers | Status, statistics, battery level, and LED ratings. |
| `05` | Write single coil | Manual load, test mode, restore, clear counters. |
| `0F` | Write multiple coils | Load-test sequence. |
| `10` | Write multiple holding registers | All register-based configuration and clock updates. |
| `2B/0E` | Read Device Identification | Device information, categories `1` and `2`, object `0`. |
| `41` | Vendor authentication | Root login/logout. |
| `43` | Vendor sparse-register read | Returns selected/available registers as nullable values. |
| `44` | Vendor physical-address read | Implemented by DLL but not invoked by this application. |
| `45` | Vendor device-ID query/set | Query uses ID `248`; set is addressed to `248`. |

## Common encodings

- Ordinary register payloads are big-endian 16-bit words.
- Most voltages, currents, temperatures, and powers use integer value ÷ `100`.
- Signed temperatures are `int16 ÷ 100`; other scaled readings are unsigned unless stated.
- A 32-bit quantity comprises `low-word, high-word` and is divided by `100`.
- Clock values at holding registers `36883..36885` are packed as `[minute, second]`, `[day, hour]`, `[year-2000, month]` (one byte each).
- Time-of-day triples are `second, minute, hour`; packed time pairs are `[hour, minute]` in network-byte order.

## Read commands

| Purpose | Request | Confirmed returned data |
|---|---|---|
| Real-time telemetry | `43 start=12544 qty=27`, then `04 start=13082 qty=3` | Sparse offsets `0..3,12..17,26`: PV V/A/W, load V/A/W, battery/device °C, SOC. Input registers: battery V and 32-bit battery current. |
| Controller status | `04 start=12800 qty=3`; `02 start=8192 qty=1` | Three status words plus over-temperature flag. Bit-to-status mapping is implemented but individual bit labels remain inferred from UI strings. |
| Statistics | `04 start=13058 qty=18` | Max/min battery V, then 8 × 32-bit values: daily/monthly/annual/total consumption and daily/monthly/annual/total charge quantity. |
| Battery/rated values | `04 start=12573 qty=1`; `43 start=12293 qty=10` | Battery/rated voltage; sparse offsets `0` and `9` are rated current values (**inferred** labels). |
| Device parameters | `43 start=36887 qty=77` | Offsets `0..3,76`: battery high/low temperature limit, controller high-temperature limit/recovery, backlight control. |
| Charging/control parameters | `43 start=36864 qty=113` | Offsets `0..14,103,107..110,112`: battery type/capacity, compensation and charge/discharge voltage thresholds, rated voltage, charge durations/SOC thresholds, charge mode. |
| Load configuration | `43 start=36894 qty=77` | Offsets `0..3,31..33,36..47,71,75,76`: light/timer thresholds, control mode, schedules, and manual default. |
| LED-load configuration | `43 start=36894 qty=100`; `04 start=12301 qty=4` | Load fields above plus LED dimming fields at offsets `34,60..62,84,85,90..99`; input block returns rated output V/A/W. |
| Date/time | `03 start=36883 qty=3` | Packed controller date/time. |
| Nominal voltage level | `04 start=12573 qty=1` | Client calculates `register / 1200 - 1`; exact enum meaning is **inferred**. |
| Device information | `2B 0E read-code=1 object=0`; repeat read-code `2` | Device-identification strings. |
| Device ID | Vendor `45` request to unit `248`, payload `00 01 01 F8` | Response contains the current device ID. |

### Sparse register read (`FC 43`)

Request PDU is `43 | start-hi | start-lo | qty-hi | qty-lo`. The response reports a requested-byte count and a data structure decoded as nullable register values; the application rejects a required offset when it is absent. It is not a standard Modbus function.

## Write and action commands

| Purpose | Request | Effect |
|---|---|---|
| Set date/time | `10 start=36883 qty=3` | Writes packed controller clock. |
| Configure device limits | `10 start=36887 qty=4`; `10 start=36963 qty=1` | Battery/controller temperature thresholds; backlight control. |
| Configure charging | `10 start=36967 qty=1`; then conditional writes to `36864`, `36971`; finally `36976 qty=1` | Rated-voltage selection, battery type/capacity and voltage thresholds, charge durations/SOC thresholds, charge mode (`0` voltage compensation, `1` SOC). |
| Configure load | Writes mode at `36925`, then mode-specific settings at `36894`, `36925..36930`, `36965`, `36969`, or `36970` | Manual, light, light+timer, single/double timer modes. See below. |
| Configure LED load | Same load controls plus `36954`, `36978`, `36984`, `36986`, `36992` | LED rated current, dimming schedule/percentages, and under-voltage behavior. |
| Manually switch load | `05 coil=2 value=on/off` | Load output control. |
| Enter/leave test mode | `05 coil=5 value=on/off` | Controller test-mode toggle. |
| Load test | `0F start=5 qty=2 values=[1, load-on]` | Enables test mode and sets load state in one request. |
| Restore defaults | `05 coil=19 value=on` | Restores controller defaults. |
| Clear statistics | `05 coil=20 value=on` | Clears recorded statistics. |
| Root login/logout | `41` with operation `0`/`1`, username stream `root`, password character data | Login expects rights result `2`; logout expects `0`. Vendor framing is DLL-confirmed; do not expose passwords. |
| Set device ID | Vendor `45`, addressed to unit `248`, payload `00 01 01 new-id` | Changes the Modbus unit ID. Validated by client as `0..247`. |

### Load mode configuration

The UI writes these logical modes: `0` manual off, `1` manual on, `2` light control, `3` light+timer, `4` single timer, `5` double timer, `6` LED-only light+timer variant. The wire-level mode encoding is confirmed by the writer but semantic register labels below are partly **inferred**:

- **Manual (`0`/`1`):** `36925=0`, `36970=0/1`.
- **Light (`2`):** `36925=1`; write four registers at `36894`: turn-on voltage/delay, turn-off voltage/delay.
- **Light + timer (`3`):** write three registers at `36925`; `36965` gets packed night period; `36894` gets four light-control values.
- **Single/double timer (`4`/`5`):** `36925=3`; `36969` selects one/two timing sections; `36930` receives one or two `[second, minute, hour]` on/off pairs.
- **LED options:** additionally write LED rated current (`36984`), current percentages (`36954` / `36992`), mode-1 timing (`36986`), and under-voltage control plus percentage (`36978`).

## Vendor commands present but unused by the solar monitor

The DLL also implements the following vendor functions. They are catalogued for completeness, but no solar-monitor operation invokes them:

| FC | Function | Request parameters |
|---|---|---|
| `44` | Read physical address | 32-bit start address, 16-bit quantity; response has 32-bit values. |
| `42` | Alter device information | Alter-code, object ID, string stream. |
| `46` | Query file information | File type plus optional start/end timestamps. |
| `47` | Delete file record | File type, action type, timestamp. |
| `48` | Read file records | File type, 32-bit start record, 32-bit quantity. |

These commands belong to the shared vendor extension library, so hardware support by this solar controller is **not confirmed**.

## Source traceability

- Operation addresses and quantities: `.refbin/SolarStationMonitor.Model.Action.ModbusOperations/*.cs`
- Register/coil constants and sparse offsets: `.refbin/SolarStationMonitor/Monitor.cs`
- Value decoding: `.refbin/SolarStationMonitor.Model.Data.ModbusDatas/*.cs` and `SolarStationMonitor/DataConverter.cs`
- Standard and vendor framing/function codes: `.refbin/Modbus.Message/*.cs` and `.refbin/Modbus.ModbusExtension.Message/*.cs`
