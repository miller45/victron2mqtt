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
    "unknown": ("UNKNOWN", "get_unknown_state"),
    "device-information": ("DEVICE_INFORMATION", "get_device_information"),
    "device-id": ("DEVICE_ID", "get_device_id"),
    "profiles": ("BATTERY_PROFILE", "get_battery_profile"),
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read values from a Victron PWM controller over RS485."
    )
    parser.add_argument(
        "command", choices=[*COMMANDS, "all"], help="Value group to read."
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
    parser.add_argument("--export", metavar="FILE", help="Save a read battery profile as JSON.")
    parser.add_argument("--import", dest="import_file", metavar="FILE", help="Write a battery profile JSON file.")
    parser.add_argument("--yes", action="store_true", help="Confirm a battery-profile write.")
    args = parser.parse_args(argv)
    if args.command != "profiles" and (args.export or args.import_file):
        parser.error("--export and --import are only available with profiles")
    if args.export and args.import_file:
        parser.error("--export and --import cannot be used together")
    if args.import_file and not args.yes:
        parser.error("--import requires --yes")
    return args


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


def read_command(client, command):
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
        if args.import_file:
            with open(args.import_file, encoding="utf-8") as profile_file:
                profile = json.load(profile_file)
            if not client.set_battery_profile(profile):
                raise OSError("failed to write battery profile")
            result = {"BATTERY_PROFILE": profile}
        else:
            result = read_command(client, args.command)
            if args.export:
                with open(args.export, "w", encoding="utf-8") as profile_file:
                    json.dump(result["BATTERY_PROFILE"], profile_file, indent=2, sort_keys=True)
                    profile_file.write("\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
