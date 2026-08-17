import serial

cmds={
    "cmdreadu1":{ #chargemode
        # Previous hardcoded request: 01 04 32 00 00 03 BE B3
        "command":"01 04 32 00 00 03".replace(" ",""),
        "exfu": int("04",16),
        "exlen": 6
    },
    "cmdreadu2": { # keine ahnung
        # Previous hardcoded request: 01 02 20 00 00 01 B2 0A
        "command":"01 02 20 00 00 01".replace(" ",""),
        "exfu": int("02",16),
        "exlen": 1
    },
    "cmdreadu3":{ # done
        # Previous hardcoded request: 01 43 31 00 00 1B 0A F2
        "command":"01 43 31 00 00 1B".replace(" ",""),
        "exfu": int("43",16),
        "exlen": int("36",16)
    },
    "cmdreadu4":{ # done(kinda)battery voltage battery current
        # Previous hardcoded request: 01 04 33 1A 00 03 9E 88
        "command":"01 04 33 1A 00 03".replace(" ",""),
        "exfu":int("04",16),
        "exlen":int("06",16)
    },
    "cmdreadu5":{ # done: statistics
        # Previous hardcoded request: 01 04 33 02 00 12 DE 83
        "command":"01 04 33 02 00 12".replace(" ",""),
        "exfu": int("04", 16),
        "exlen": int("24",16)
    }

}
cmdreadcontrolpara1="0104311d0001af30" #elen
cmdreadcontrolpara2="01433005000adb03"
cmdreadcontrolpara3="014390000071a921"
cmdreadtimepara=   '010390130003d90e'
DEVICE_UNIT_ID = 1
DEVICE_ID_DISCOVERY_UNIT_ID = 248
CONTROL_PARAMETERS_START = 36864
CONTROL_PARAMETERS_COUNT = 113
CONTROL_PARAMETER_OFFSETS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 103, 107, 108, 109, 110, 112
)
BATTERY_PROFILES = {
    0: "user",
    1: "lead_acid_maintenance_free",
    2: "gel",
    3: "lead_acid_flooded",
}
charge_mode_code="0x3200"
statistic_code="0x3302"
battery_code="0x331a"


def hex_to_binary(hextext):
    import array
    bvals = []
    for x in range(0,len(hextext),2):
        hexa = hextext[x:x+2]
        hexb = int(hexa,16)
        bvals.append(hexb)
    res = array.array("B",bvals)
    return res


def modbus_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class VictronClient:


    def __init__(self, serial_port, validate_checksum=True):
        self.serial_port = serial_port
        self.validate_checksum = validate_checksum
    def debugo(self,msg):
        print(msg)

    def read_pwm_data(self, name):
        md = "deviceid"
        curcmdu = cmds[name]
        command = bytes(hex_to_binary(curcmdu['command']))
        bincmd = command + modbus_crc(command).to_bytes(2, byteorder="little")
        reg_nu = int.from_bytes(bincmd[2:4], byteorder="big")

        curexlen = curcmdu['exlen']
        curexfu = curcmdu['exfu']
        self.debugo(f"send cmd{curexfu} reg_nu " + hex(reg_nu))
        # bincmd= hex_to_binary(cmdreadu2)
        # #hex_to_binary(cmdreadtimepara)#cmdreaddeviceid
        # print(len(bincmd))
        with serial.Serial(self.serial_port, 115200, timeout=1) as ser:
            ser.write(bincmd)
            header = ser.read(2)
            slid = int.from_bytes(header[0:1], byteorder='big')
            fucode = int.from_bytes(header[1:2], byteorder='big')
            if fucode == curexfu:
                blen = int.from_bytes(ser.read(1), byteorder="big")
                all = ser.read(blen + 2)
                if len(all) != blen + 2:
                    self.debugo("incomplete response")
                    return None

                data = all[:-2]
                received_crc = int.from_bytes(all[-2:], byteorder="little")
                response = header + bytes([blen]) + data
                if modbus_crc(response) != received_crc:
                    self.debugo("invalid response checksum")
                    if self.validate_checksum:
                        return None

                self.debugo(f"{blen} ex{curexlen}")
                return self.decode_for_fu(fucode, reg_nu, data)
                # print(hex(modbus_crc(data)))
                # print(check_crc(data))
                pass
            else:
                self.debugo(f"unexpected fucode " + hex(fucode))

    def dumpallvalues(self, data, dlen):
        for i in range(0, int(dlen / 2)):
            di = i * 2
            big = int.from_bytes(data[di:di + 2], byteorder="big")
            #  lit=int.from_bytes(data[di:di+2],byteorder="little")
            shif = int.from_bytes(data[di + 1:di + 3], byteorder="big")
            # print(f"#{di} big {big} shif {shif}")
            #self.debugo("{di}\t{big}")

    def decode_for_fu(self, fun, reg_nu, data):
        reg_nu_text = hex(reg_nu)
        if fun == 4 and hex(reg_nu) == battery_code:

            return {
                "battery_voltage": int.from_bytes(data[0:2], byteorder="big")/100,
                "battery_current": int.from_bytes(data[2:4], byteorder="big")/100
            }
        if fun == 4 and hex(reg_nu) == charge_mode_code:
            loadon = (int.from_bytes(data[5:6], byteorder="big") & 1) > 0
            chargmode = int.from_bytes(data[3:4], byteorder="big")
            # mode f equi mode b
            cmods = {
                15: "equilibrate",
                11: "boostcharge",
                7: "float",
                1: "notcharging"
            }
            res = {
                "load": "on" if loadon else "off",
                "chargemode": "unknown"
            }
            if chargmode in cmods:
                res['chargemode'] = cmods[chargmode]

            return res
        if fun == 4 and hex(reg_nu) == statistic_code:
            # dumpallvalues(data,len(data)-2)

            return {
                "regnu": "3302",
                "battery_max_voltage": int.from_bytes(data[0:2], byteorder="big") / 100,
                "battery_min_voltage": int.from_bytes(data[2:4], byteorder="big") / 100,
                # these all might be actually two 16 bit numbers
                "consumed_kwh_daily": int.from_bytes(data[4:6], byteorder="big") / 100,
                "consumed_kwh_monthly": int.from_bytes(data[8:10], byteorder="big") / 100,
                "consumed_kwh_annual": int.from_bytes(data[12:14], byteorder="big") / 100,
                "consumed_kwh_total": int.from_bytes(data[16:18], byteorder="big") / 100,
                "generated_kwh_daily": int.from_bytes(data[20:22], byteorder="big") / 100,
                # these might be actually two 16 bit numbers
                "generated_kwh_monthly": int.from_bytes(data[24:26], byteorder="big") / 100,
                "generated_kwh_annual": int.from_bytes(data[28:30], byteorder="big") / 100,
                "generated_kwh_total": int.from_bytes(data[32:34], byteorder="big") / 100,
            }
            # print(f"load is {loadon}")
        if fun == 2:
            #self.dumpallvalues(data, len(data))
            return {
                "fu": int.from_bytes(data[0:1],byteorder="big")
            }
        if fun == int("43", 16):
            # dumpallvalues(data,len(data)-2)
            # bei load off 14 auf 7 16-34 auf0
            return {  # array 4,6,8,(10ist immer0); 14,16,18,
                # 20-32 load related
                # 4-8 array related
                # 12-18 battery related
                "array_voltage": int.from_bytes(data[4:6], byteorder="big") / 100,
                "array_current": int.from_bytes(data[6:8], byteorder="big") / 100,
                "battery_voltage": int.from_bytes(data[12:14], byteorder="big") / 100,
                "some_current": int.from_bytes(data[14:16], byteorder="big") / 100,
                "load_voltage1": int.from_bytes(data[20:22], byteorder="big") / 100,
                "load_current1": int.from_bytes(data[24:26], byteorder="big") / 1000,
                "load_voltage2": int.from_bytes(data[28:30], byteorder="big") / 100,
                "load_current2": int.from_bytes(data[32:34], byteorder="big") / 1000,
                "load_voltage3": int.from_bytes(data[28:30], byteorder="big") / 100,
                "load_current3": int.from_bytes(data[32:34], byteorder="big") / 1000,
                "temp1": int.from_bytes(data[36:38], byteorder="big") / 100,
                "temp2": int.from_bytes(data[38:40], byteorder="big") / 100,
                "temp3": int.from_bytes(data[40:42], byteorder="big") / 100,
                "battery_soc": int.from_bytes(data[42:44], byteorder="big")
            }

        return {}

    def get_simple_state(self):
        return self.read_pwm_data('cmdreadu1')
    def get_statistics(self):
        return self.read_pwm_data('cmdreadu5')
    def get_detailed_states(self):
        return self.read_pwm_data('cmdreadu3')

    def get_battery_details(self):
        return self.read_pwm_data('cmdreadu4')
    def get_unknown_state(self):
        return self.read_pwm_data('cmdreadu2')

    def get_battery_profile(self):
        data = self._send_request(
            bytes((
                DEVICE_UNIT_ID,
                0x43,
                CONTROL_PARAMETERS_START >> 8,
                CONTROL_PARAMETERS_START & 0xFF,
                CONTROL_PARAMETERS_COUNT >> 8,
                CONTROL_PARAMETERS_COUNT & 0xFF,
            )),
            0x43,
        )
        if data is None:
            return None

        registers = self._decode_sparse_registers(data, CONTROL_PARAMETERS_COUNT)
        if registers is None:
            return None
        if any(registers[offset] is None for offset in CONTROL_PARAMETER_OFFSETS):
            self.debugo("incomplete battery profile response")
            return None

        values = [registers[offset] for offset in CONTROL_PARAMETER_OFFSETS]
        battery_type = values[0]
        return {
            "battery_type": BATTERY_PROFILES.get(battery_type, "unknown"),
            "battery_type_code": battery_type,
            "battery_capacity_ah": values[1],
            "temperature_compensation": -values[2] / 100,
            "overvoltage_cutoff_voltage": values[3] / 100,
            "charge_limit_voltage": values[4] / 100,
            "overvoltage_recovery_voltage": values[5] / 100,
            "equalization_voltage": values[6] / 100,
            "boost_voltage": values[7] / 100,
            "float_voltage": values[8] / 100,
            "boost_recovery_voltage": values[9] / 100,
            "low_voltage_recovery_voltage": values[10] / 100,
            "warning_recovery_voltage": values[11] / 100,
            "low_voltage_warning_voltage": values[12] / 100,
            "low_voltage_cutoff_voltage": values[13] / 100,
            "discharge_limit_voltage": values[14] / 100,
            "rated_voltage_level": values[15],
            "equalization_duration_minutes": values[16],
            "boost_duration_minutes": values[17],
            "battery_charge_soc": values[18],
            "battery_discharge_soc": values[19],
            "charge_mode": "soc" if values[20] == 1 else "voltage_compensation",
            "charge_mode_code": values[20],
        }

    def set_battery_profile(self, profile):
        values = self._encode_battery_profile(profile)
        battery_type, charge_mode = values[0], values[20]

        writes = [(36967, values[15:16])]
        writes.append((36864, values[:15] if battery_type == 0 else values[:3]))
        writes.append((36971, values[16:20] if charge_mode == 1 else values[16:18]))
        writes.append((36976, values[20:21]))
        for start_address, write_values in writes:
            if not self._write_holding_registers(start_address, write_values):
                return None
        return True

    def _encode_battery_profile(self, profile):
        if not isinstance(profile, dict):
            raise ValueError("battery profile must be a JSON object")

        required_keys = {
            "battery_type", "battery_type_code", "battery_capacity_ah",
            "temperature_compensation", "overvoltage_cutoff_voltage",
            "charge_limit_voltage", "overvoltage_recovery_voltage",
            "equalization_voltage", "boost_voltage", "float_voltage",
            "boost_recovery_voltage", "low_voltage_recovery_voltage",
            "warning_recovery_voltage", "low_voltage_warning_voltage",
            "low_voltage_cutoff_voltage", "discharge_limit_voltage",
            "rated_voltage_level", "equalization_duration_minutes",
            "boost_duration_minutes", "battery_charge_soc", "battery_discharge_soc",
            "charge_mode", "charge_mode_code",
        }
        missing_keys = required_keys - profile.keys()
        if missing_keys:
            raise ValueError("battery profile is missing: " + ", ".join(sorted(missing_keys)))

        battery_type = self._profile_integer(profile, "battery_type_code")
        if BATTERY_PROFILES.get(battery_type) != profile["battery_type"]:
            raise ValueError("battery_type does not match battery_type_code")
        charge_mode = self._profile_integer(profile, "charge_mode_code")
        if charge_mode not in (0, 1):
            raise ValueError("charge_mode_code must be 0 or 1")
        if profile["charge_mode"] != ("soc" if charge_mode else "voltage_compensation"):
            raise ValueError("charge_mode does not match charge_mode_code")

        return [
            battery_type,
            self._profile_integer(profile, "battery_capacity_ah"),
            self._profile_scaled_integer(profile, "temperature_compensation", -100),
            *[self._profile_scaled_integer(profile, name, 100) for name in (
                "overvoltage_cutoff_voltage", "charge_limit_voltage",
                "overvoltage_recovery_voltage", "equalization_voltage", "boost_voltage",
                "float_voltage", "boost_recovery_voltage", "low_voltage_recovery_voltage",
                "warning_recovery_voltage", "low_voltage_warning_voltage",
                "low_voltage_cutoff_voltage", "discharge_limit_voltage",
            )],
            self._profile_integer(profile, "rated_voltage_level"),
            self._profile_integer(profile, "equalization_duration_minutes"),
            self._profile_integer(profile, "boost_duration_minutes"),
            self._profile_integer(profile, "battery_charge_soc"),
            self._profile_integer(profile, "battery_discharge_soc"),
            charge_mode,
        ]

    @staticmethod
    def _profile_integer(profile, name):
        value = profile[name]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFF:
            raise ValueError(f"{name} must be an integer between 0 and 65535")
        return value

    @staticmethod
    def _profile_scaled_integer(profile, name, scale):
        value = profile[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
        scaled_value = round(value * scale)
        if scaled_value < 0 or scaled_value > 0xFFFF or scaled_value != value * scale:
            raise ValueError(f"{name} has an invalid value or precision")
        return scaled_value

    def _write_holding_registers(self, start_address, values):
        payload = b"".join(value.to_bytes(2, byteorder="big") for value in values)
        request = bytes((
            DEVICE_UNIT_ID,
            0x10,
            start_address >> 8,
            start_address & 0xFF,
            len(values) >> 8,
            len(values) & 0xFF,
            len(payload),
        )) + payload
        request_with_crc = request + modbus_crc(request).to_bytes(2, byteorder="little")

        with serial.Serial(self.serial_port, 115200, timeout=1) as ser:
            ser.write(request_with_crc)
            response = ser.read(8)
        if len(response) != 8:
            self.debugo("incomplete write response")
            return None
        if response[:6] != request[:6]:
            self.debugo("unexpected write response")
            return None
        received_crc = int.from_bytes(response[6:], byteorder="little")
        if modbus_crc(response[:6]) != received_crc:
            self.debugo("invalid response checksum")
            if self.validate_checksum:
                return None
        return True

    def _decode_sparse_registers(self, data, register_count):
        table_length = (register_count + 7) // 8
        if len(data) < 1 + table_length:
            self.debugo("incomplete sparse register response")
            return None
        if data[0] != register_count * 2:
            self.debugo("unexpected sparse register response length")
            return None

        present_offsets = []
        for table_index, value in enumerate(reversed(data[1 : 1 + table_length])):
            present_offsets.extend(
                table_index * 8 + bit for bit in range(8) if value & (1 << bit)
            )
        present_offsets = [offset for offset in present_offsets if offset < register_count]
        value_data = data[1 + table_length :]
        if len(value_data) != len(present_offsets) * 2:
            self.debugo("invalid sparse register response")
            return None

        registers = [None] * register_count
        for index, offset in enumerate(present_offsets):
            registers[offset] = int.from_bytes(
                value_data[index * 2 : index * 2 + 2], byteorder="big"
            )
        return registers

    def _send_request(self, request, expected_function):
        frame = bytes(request)
        request_with_crc = frame + modbus_crc(frame).to_bytes(2, byteorder="little")

        with serial.Serial(self.serial_port, 115200, timeout=1) as ser:
            ser.write(request_with_crc)
            header = ser.read(2)
            if len(header) != 2:
                self.debugo("incomplete response header")
                return None

            unit_id, function_code = header
            if function_code != expected_function:
                self.debugo(f"unexpected fucode {function_code:#x}")
                return None

            return self._read_vendor_response(ser, header)

    def _read_vendor_response(self, ser, header):
        payload = bytearray()
        while True:
            chunk = ser.read(1)
            if not chunk:
                self.debugo("incomplete response")
                return None
            payload.extend(chunk)

            if len(payload) >= 2:
                candidate = header + payload[:-2]
                received_crc = int.from_bytes(payload[-2:], byteorder="little")
                if modbus_crc(candidate) == received_crc:
                    return bytes(payload[:-2])

    def get_device_information(self):
        information = {}
        for read_code in (1, 2):
            data = self._send_request(
                bytes((DEVICE_UNIT_ID, 0x2B, 0x0E, read_code, 0)), 0x2B
            )
            if data is None:
                return None
            if len(data) < 6 or data[0] != 0x0E or data[1] != read_code:
                self.debugo("invalid device information response")
                return None

            object_count = data[5]
            offset = 6
            for _ in range(object_count):
                if offset + 2 > len(data):
                    self.debugo("incomplete device information object")
                    return None
                object_id, length = data[offset : offset + 2]
                offset += 2
                if offset + length > len(data):
                    self.debugo("incomplete device information value")
                    return None
                information[str(object_id)] = data[offset : offset + length].decode(
                    "ascii", errors="replace"
                )
                offset += length
        return information

    def get_device_id(self):
        data = self._send_request(
            bytes((DEVICE_ID_DISCOVERY_UNIT_ID, 0x45, 0, 1, 1, DEVICE_ID_DISCOVERY_UNIT_ID)),
            0x45,
        )
        if data is None:
            return None
        if len(data) != 1:
            self.debugo("invalid device ID response")
            return None
        return data[0]
