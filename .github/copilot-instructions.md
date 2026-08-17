# Copilot Instructions

## Project overview

This is a small Python service and CLI for Victron PWM solar controllers connected over RS485/Modbus RTU.

- `victroncom.py` is the protocol layer. `VictronClient` constructs Modbus frames, appends/checks little-endian CRC16 values, opens the serial port at `115200` baud with a one-second timeout, and decodes controller payloads into JSON-compatible dictionaries.
- `victron_cli.py` is the one-shot command-line interface. Its `COMMANDS` mapping is the shared command-to-client-method and JSON-output-name contract. It accepts an explicit `--port` or reads `[serial] serial_port` from `config.ini`; checksum validation is on unless `--ignore-checksum` is supplied.
- `main.py` is the long-running bridge. It reads `config.ini`, polls the five legacy telemetry groups every 60 seconds, and publishes both individual and aggregate payloads through `MQTTComm`.
- `mqttcom.py` wraps Paho MQTT. It publishes under `tele/<base_topic>/STATE<suffix>` and maintains the retained `tele/<base_topic>/LWT` status (`Online`/`Offline`).
- `refdocs/solar-charger-binary-modbus-commands.md` is the protocol authority for register offsets, encodings, supported vendor functions, and evidence/confidence. `.refbin/` is ignored reference/decompiled material; do not treat it as application source.

## Setup and commands

Install runtime dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Run the full test suite (standard-library `unittest`):

```sh
python3 -m unittest discover -s tests -v
```

Run one test module or one test method:

```sh
python3 -m unittest tests.test_victroncom -v
python3 -m unittest tests.test_victroncom.SerialTransportTests.test_sends_command_and_decodes_valid_response -v
```

There is no configured lint or formatting tool.

Run a hardware CLI read:

```sh
python3 victron_cli.py --port /dev/ttyUSB0 state
python3 victron_cli.py --port /dev/ttyUSB0 device-information
python3 victron_cli.py --port /dev/ttyUSB0 all
```

Copy `config.ini.example` to the untracked `config.ini` before running `main.py` or using the CLI without `--port`. `config.ini` contains local connection details and must not be committed.

## Protocol and data conventions

- Preserve Modbus framing: request CRC16 is appended low byte first; ordinary register words are big-endian. Validate response CRCs by default. Hardware/protocol changes need fixture-based tests rather than a physical controller.
- Keep decoded values JSON-compatible and retain the existing output keys and units. Most measurements are unsigned register values divided by `100`; selected currents use `/1000`. Confirm new offsets, signedness, and scaling against `refdocs/` before adding them.
- `read_pwm_data()` handles the fixed-length legacy command definitions in `cmds`; device-information and device-ID reads use `_send_request()` plus `_read_vendor_response()` because their vendor responses are variable length. Use the matching transport path for a new command.
- Treat incomplete, unexpected-function, malformed, and invalid-checksum responses as failed reads (`None`) unless checksum validation was explicitly disabled. `debugo` is intentionally replaceable so the CLI can emit clean JSON.
- Tests install a stub `serial` module before importing `victroncom`, and mock `serial.Serial` with `FakeSerial`. Keep tests independent of pyserial and hardware.
- The service's aggregate MQTT payload intentionally uses the existing `UKNOWN` spelling; avoid silently renaming published topics or JSON keys because subscribers may rely on them.
