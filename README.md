# vitron2mqtt

Read stats from a Victron PWM solar controller over RS485 and publish them via MQTT.

## Command-line reads

Use `victron_cli.py` to read a value group once and print pretty-formatted JSON:

```sh
python3 victron_cli.py --port /dev/ttyUSB0 state
python3 victron_cli.py --port /dev/ttyUSB0 statistics
python3 victron_cli.py --port /dev/ttyUSB0 details
python3 victron_cli.py --port /dev/ttyUSB0 battery
python3 victron_cli.py --port /dev/ttyUSB0 charge-current
python3 victron_cli.py --port /dev/ttyUSB0 unknown
python3 victron_cli.py --port /dev/ttyUSB0 all
python3 victron_cli.py --port /dev/ttyUSB0 --battery-maximum-current 10.0 set-battery-maximum-current
```

`set-battery-maximum-current` writes the MPPT battery charge-current limit. The value must be between `0` and `6553.5` amps in `0.1`-amp increments.

When `--port` is omitted, the CLI reads `[serial] serial_port` from `config.ini`. Supply a different configuration file with `--config path/to/config.ini`.

Response checksums are validated by default. Use `--ignore-checksum` to warn about invalid checksums while still decoding their payloads.
