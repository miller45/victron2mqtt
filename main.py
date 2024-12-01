import mqttcom
import victroncom
import configparser
import math
import time
import syslog

print("Starting victron2mqtt")

hpConfig = configparser.ConfigParser()
hpConfig.read("config.ini")



def slog(msg):
    syslog.syslog(msg)
    print(msg)

def connectthat():
    victronClient = victroncom.VictronClient(hpConfig["serial"]["serial_port"])
    return victronClient

def connecit():
    doinit = True

    while doinit:
        try:
            mqttClient = mqttcom.MQTTComm(hpConfig["mqtt"]["server_address"], hpConfig["mqtt"]["base_topic"])

            doinit = False
            mqttClient.ping()
            return mqttClient

        except BaseException as error:
            slog('An exception occurred during init')  #: {}'.format(error))
            slog('{}: {}'.format(type(error).__name__, error))
            if type(error) == KeyboardInterrupt:
                exit(0)
            slog("restarting after 5 secs")
            time.sleep(5)
    return None


mqttClient = connecit()
victronClient = connectthat()

lctime = math.trunc(time.time() * 1000)
pollPeriod = 100
check_period = 5000
tele_period = 60000

lstateCounter = 0
ltime = 0
lteletime = 0

spamltime = 0

onon = True

while onon:
    try:
        while True:
            currtime = math.trunc(time.time() * 1000)  # time in microseconds
            if currtime - pollPeriod > ltime:
                delta = currtime - ltime

                ltime = currtime
            if currtime - check_period > lctime:
                if not mqttClient.client.is_connected():
                    slog("not connected retrying")
                    mqttClient = connecit()
                lctime = currtime
            if currtime - tele_period > lteletime:
                gstate=victronClient.get_simple_state()
                print(gstate)
                mqttClient.send_tele(1, gstate)
                lteletime = currtime

            if lstateCounter != mqttClient.stateCounter:
                lstateCounter = mqttClient.stateCounter
            time.sleep(0.01)

    except BaseException as error:
        slog('An exception occurred during onon')  #: {}'.format(error))
        slog('{}: {}'.format(type(error).__name__, error))
        if type(error) == KeyboardInterrupt:
            exit(0)
        slog("restarting after 5 secs")
        time.sleep(5)
    except:
        slog("exception occurred restarting after 1 secs")
        time.sleep(1)
