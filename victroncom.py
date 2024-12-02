import serial

cmds={
    "cmdreadu1":{ #chargemode
        "command":"01 04 32 00 00 03 BE B3".replace(" ",""),
        "exfu": int("04",16),
        "exlen": 6
    },
    "cmdreadu2": { # keine ahnung
        "command":"01 02 20 00 00 01 B2 0A".replace(" ",""),
        "exfu": int("02",16),
        "exlen": 1
    },
    "cmdreadu3":{ # done
        "command":"01 43 31 00 00 1B 0A F2".replace(" ",""),
        "exfu": int("43",16),
        "exlen": int("36",16)
    },
    "cmdreadu4":{ # done(kinda)battery voltage battery current
        "command":"01 04 33 1A 00 03 9E 88".replace(" ",""),
        "exfu":int("04",16),
        "exlen":int("06",16)
    },
    "cmdreadu5":{ # done: statistics
        "command":"01 04 33 02 00 12 DE 83".replace(" ",""),
        "exfu": int("04", 16),
        "exlen": int("24",16)
    }

}
cmdreadcontrolpara1="0104311d0001af30" #elen
cmdreadcontrolpara2="01433005000adb03"
cmdreadcontrolpara3="014390000071a921"
cmdreadtimepara=   '010390130003d90e'
cmdreaddeviceid="012b0e01007077"
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

class VictronClient:


    def __init__(self, serial_port):
        self.serial_port = serial_port
    def debugo(self,msg):
        print(msg)

    def read_pwm_data(self, name):
        md = "deviceid"
        curcmdu = cmds[name]
        bincmd = hex_to_binary(curcmdu['command'])  # read load on/of
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
                self.debugo(f"{blen} ex{curexlen}")
                decm = self.decode_for_fu(fucode, reg_nu, all)
                # print(binary_to_hex(all))
                datalen = len(all) - 2
                data = all[0:datalen]
                return decm
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




