#!/usr/bin/env python3
"""Read Victron PWM controller values from the command line."""
import argparse
import configparser
import json
import sys

try:
    import victroncom
except ModuleNotFoundError:
    victroncom = None


COMMANDS = {
    "state": ("GLOBALSTATE", "get_simple_state"),
    "statistics": ("STATISTICS", "get_statistics"),
    "details": ("DETAILS", "get_detailed_states"),
    "battery": ("BATTERY", "get_battery_details"),
    "charge-current": ("BATTERY_CHARGE_CURRENT", "get_battery_charge_current"),
    "unknown": ("UNKNOWN", "get_unknown_state"),
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read values from a Victron PWM controller over RS485."
    )
    parser.add_argument(
        "command", choices=[*COMMANDS, "all", "set-battery-maximum-current"], help="Value group to read or setting to update."
    )
    parser.add_argument(
        "--battery-maximum-current",
        type=float,
        metavar="AMPS",
        help="Set the battery charge-current limit in amps (for set-battery-maximum-current).",
    )
    parser.add_argument("--port", help="Serial port, for example /dev/ttyUSB0.")
    parser.add_argument(
        "--config", default="config.ini", help="Configuration file used when --port is omitted."
    )
    parser.add_argument(
        "--ignore-checksum",
        action="store_true",
        help="Warn about invalid response checksums but decode their payloads.",
    )
    return parser.parse_args(argv)


def get_serial_port(port, config_path):
    if port:
        return port

    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise ValueError(
            f"serial port was not supplied and configuration file {config_path!r} could not be read"
        )

    try:
        return config["serial"]["serial_port"]
    except KeyError as error:
        raise ValueError(
            f"serial port was not supplied and {config_path!r} lacks [serial] serial_port"
        ) from error


def read_command(client, command, battery_maximum_current=None):
    if command == "set-battery-maximum-current":
        if battery_maximum_current is None:
            raise ValueError("--battery-maximum-current is required for set-battery-maximum-current")
        return {"BATTERY_MAXIMUM_CURRENT": client.set_battery_maximum_current(battery_maximum_current)}

    if command == "all":
        return {
            output_name: getattr(client, method_name)()
            for output_name, method_name in COMMANDS.values()
        }

    output_name, method_name = COMMANDS[command]
    return {output_name: getattr(client, method_name)()}


def main(argv=None):
    args = parse_args(argv)
    if victroncom is None:
        print("error: pyserial is required; install dependencies with pip install -r requirements.txt", file=sys.stderr)
        return 1

    try:
        port = get_serial_port(args.port, args.config)
        client = victroncom.VictronClient(port, validate_checksum=not args.ignore_checksum)
        client.debugo = lambda _message: None
        result = read_command(client, args.command, args.battery_maximum_current)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
