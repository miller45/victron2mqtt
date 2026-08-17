"""Unit tests for Victron RS485 command decoding and transport."""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


# Keep tests independent of hardware-only pyserial installation.
sys.modules.setdefault("serial", types.ModuleType("serial"))
victroncom = importlib.import_module("victroncom")


class FakeSerial:
    def __init__(self, response):
        self.response = bytearray(response)
        self.writes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, data):
        self.writes.append(data)

    def read(self, length):
        result = bytes(self.response[:length])
        del self.response[:length]
        return result


class HexToBinaryTests(unittest.TestCase):
    def test_converts_hex_pairs_to_byte_array(self):
        self.assertEqual(victroncom.hex_to_binary("01aBff").tolist(), [1, 171, 255])


class DecodeTests(unittest.TestCase):
    def setUp(self):
        self.client = victroncom.VictronClient("/dev/null")

    def test_decodes_battery_measurements(self):
        data = bytes.fromhex("0964fe0c0000")

        self.assertEqual(
            self.client.decode_for_fu(4, 0x331A, data),
            {"battery_voltage": 24.04, "battery_current": 650.36},
        )

    def test_decodes_charge_mode_and_load_state(self):
        data = bytes([0, 0, 0, 11, 0, 1])

        self.assertEqual(
            self.client.decode_for_fu(4, 0x3200, data),
            {"load": "on", "chargemode": "boostcharge"},
        )

    def test_marks_unknown_charge_mode(self):
        data = bytes([0, 0, 0, 99, 0, 0])

        self.assertEqual(
            self.client.decode_for_fu(4, 0x3200, data),
            {"load": "off", "chargemode": "unknown"},
        )

    def test_decodes_statistics_at_documented_offsets(self):
        data = b"".join(value.to_bytes(2, "big") for value in range(1, 19))

        result = self.client.decode_for_fu(4, 0x3302, data)

        self.assertEqual(result["battery_max_voltage"], 0.01)
        self.assertEqual(result["consumed_kwh_monthly"], 0.05)
        self.assertEqual(result["generated_kwh_total"], 0.17)

    def test_decodes_function_two_response(self):
        self.assertEqual(self.client.decode_for_fu(2, 0, b"\x7f"), {"fu": 127})

    def test_returns_empty_mapping_for_unknown_function(self):
        self.assertEqual(self.client.decode_for_fu(99, 0, b""), {})


class SerialTransportTests(unittest.TestCase):
    def test_sends_command_and_decodes_valid_response(self):
        # slave id, function code, payload length, payload, CRC (little-endian)
        response = bytes([1, 4, 6]) + bytes.fromhex("0964fe0c0000")
        serial_port = FakeSerial(response + victroncom.modbus_crc(response).to_bytes(2, "little"))
        serial_constructor = Mock(return_value=serial_port)
        client = victroncom.VictronClient("/dev/ttyUSB0")
        client.debugo = Mock()

        with patch.object(victroncom.serial, "Serial", serial_constructor, create=True):
            result = client.read_pwm_data("cmdreadu4")

        self.assertEqual(result, {"battery_voltage": 24.04, "battery_current": 650.36})
        serial_constructor.assert_called_once_with("/dev/ttyUSB0", 115200, timeout=1)
        self.assertEqual(serial_port.writes, [bytes.fromhex("0104331a00039e88")])

    def test_calculates_crc_for_cmdreadu1_request(self):
        response = bytes([1, 4, 6]) + bytes([0, 0, 0, 11, 0, 1])
        serial_port = FakeSerial(response + victroncom.modbus_crc(response).to_bytes(2, "little"))
        client = victroncom.VictronClient("/dev/ttyUSB0")
        client.debugo = Mock()

        with patch.object(victroncom.serial, "Serial", return_value=serial_port, create=True):
            client.read_pwm_data("cmdreadu1")

        self.assertEqual(serial_port.writes, [bytes.fromhex("010432000003beb3")])

    def test_rejects_response_with_invalid_checksum(self):
        serial_port = FakeSerial(bytes([1, 4, 6]) + bytes.fromhex("0964fe0c0000") + b"\x00\x00")
        client = victroncom.VictronClient("/dev/ttyUSB0")
        client.debugo = Mock()

        with patch.object(victroncom.serial, "Serial", return_value=serial_port, create=True):
            self.assertIsNone(client.read_pwm_data("cmdreadu4"))

        client.debugo.assert_any_call("invalid response checksum")

    def test_warns_but_decodes_invalid_checksum_when_validation_is_disabled(self):
        serial_port = FakeSerial(bytes([1, 4, 6]) + bytes.fromhex("0964fe0c0000") + b"\x00\x00")
        client = victroncom.VictronClient("/dev/ttyUSB0", validate_checksum=False)
        client.debugo = Mock()

        with patch.object(victroncom.serial, "Serial", return_value=serial_port, create=True):
            result = client.read_pwm_data("cmdreadu4")

        self.assertEqual(result, {"battery_voltage": 24.04, "battery_current": 650.36})
        client.debugo.assert_any_call("invalid response checksum")

    def test_rejects_incomplete_response(self):
        serial_port = FakeSerial(bytes([1, 4, 6]) + bytes.fromhex("0964fe0c"))
        client = victroncom.VictronClient("/dev/ttyUSB0")
        client.debugo = Mock()

        with patch.object(victroncom.serial, "Serial", return_value=serial_port, create=True):
            self.assertIsNone(client.read_pwm_data("cmdreadu4"))

        client.debugo.assert_any_call("incomplete response")

    def test_returns_none_for_unexpected_function_code(self):
        serial_port = FakeSerial(b"\x01\x03")
        client = victroncom.VictronClient("/dev/ttyUSB0")
        client.debugo = Mock()

        with patch.object(victroncom.serial, "Serial", return_value=serial_port, create=True):
            self.assertIsNone(client.read_pwm_data("cmdreadu4"))

        client.debugo.assert_any_call("unexpected fucode 0x3")


if __name__ == "__main__":
    unittest.main()
