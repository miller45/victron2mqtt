"""Unit tests for the Victron command-line interface."""
import importlib
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, mock_open, patch


sys.modules.setdefault("serial", types.ModuleType("serial"))
victron_cli = importlib.import_module("victron_cli")


class SerialPortTests(unittest.TestCase):
    def test_uses_explicit_port(self):
        self.assertEqual(
            victron_cli.get_serial_port("/dev/ttyUSB0", "does-not-exist.ini"),
            "/dev/ttyUSB0",
        )

    def test_reads_port_from_config(self):
        with patch("victron_cli.configparser.ConfigParser") as parser_class:
            parser = parser_class.return_value
            parser.read.return_value = ["config.ini"]
            parser.__getitem__.return_value = {"serial_port": "/dev/ttyS0"}

            self.assertEqual(victron_cli.get_serial_port(None, "config.ini"), "/dev/ttyS0")


class CliTests(unittest.TestCase):
    def test_reads_named_command_and_prints_json(self):
        client = Mock()
        client.get_battery_details.return_value = {"battery_voltage": 24.04}
        output = io.StringIO()

        with patch("victron_cli.victroncom.VictronClient", return_value=client) as client_class:
            with redirect_stdout(output):
                result = victron_cli.main(["--port", "/dev/ttyUSB0", "battery"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), '{\n  "BATTERY": {\n    "battery_voltage": 24.04\n  }\n}\n')
        self.assertTrue(callable(client.debugo))
        client_class.assert_called_once_with("/dev/ttyUSB0", validate_checksum=True)

    def test_ignore_checksum_disables_checksum_rejection(self):
        client = Mock()
        client.get_battery_details.return_value = {"battery_voltage": 24.04}

        with patch("victron_cli.victroncom.VictronClient", return_value=client) as client_class:
            self.assertEqual(
                victron_cli.main(["--port", "/dev/ttyUSB0", "--ignore-checksum", "battery"]),
                0,
            )

        client_class.assert_called_once_with("/dev/ttyUSB0", validate_checksum=False)

    def test_reads_all_command(self):
        client = Mock()
        for _output_name, method_name in victron_cli.COMMANDS.values():
            getattr(client, method_name).return_value = {"value": method_name}

        self.assertEqual(victron_cli.read_command(client, "all"), {
            output_name: {"value": method_name}
            for output_name, method_name in victron_cli.COMMANDS.values()
        })

    def test_reads_battery_profile(self):
        client = Mock()
        client.get_battery_profile.return_value = {"battery_type": "lead_acid_flooded"}

        self.assertEqual(
            victron_cli.read_command(client, "profiles"),
            {"BATTERY_PROFILE": {"battery_type": "lead_acid_flooded"}},
        )

    def test_exports_battery_profile(self):
        client = Mock()
        client.get_battery_profile.return_value = {"battery_type": "lead_acid_flooded"}
        profile_file = mock_open()

        with patch("victron_cli.victroncom.VictronClient", return_value=client):
            with patch("builtins.open", profile_file):
                self.assertEqual(
                    victron_cli.main(["--port", "/dev/ttyUSB0", "profiles", "--export", "profile.json"]),
                    0,
                )

        profile_file.assert_called_once_with("profile.json", "w", encoding="utf-8")
        self.assertIn(
            "lead_acid_flooded",
            "".join(call.args[0] for call in profile_file().write.call_args_list),
        )

    def test_imports_battery_profile_after_confirmation(self):
        client = Mock()
        profile_file = mock_open(read_data='{"battery_type": "gel"}')

        with patch("victron_cli.victroncom.VictronClient", return_value=client):
            with patch("builtins.open", profile_file):
                self.assertEqual(
                    victron_cli.main(["--port", "/dev/ttyUSB0", "profiles", "--import", "profile.json", "--yes"]),
                    0,
                )

        client.set_battery_profile.assert_called_once_with({"battery_type": "gel"})


if __name__ == "__main__":
    unittest.main()
