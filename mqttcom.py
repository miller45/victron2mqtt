import json

import paho.mqtt.client as mqtt
import posixpath as path
import syslog


class Eintrag:
    nextEventTime = -1
    nextEventMsg = ""
    nextEventTgt = ""

    def __init__(self, event_time, event_msg, event_tgt):
        self.nextEventTime = event_time
        self.nextEventMsg = event_msg
        self.nextEventTgt = event_tgt


class MQTTComm:
    swState = {}
    last_dir = {}  # last direction of shutters
    stateCounter = 0
    timeMS = 0
    connected = False
    eintraege = []

    def __init__(self, server_address, real_topic):
        self.server_address = server_address
        self.real_topic = real_topic
        self.result_topic = path.join("stat", real_topic)
        self.tele_topic = path.join("tele", real_topic)
        self.client = mqtt.Client()
        self.connect()

    def connect(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.will_set(path.join(self.tele_topic,"LWT"), payload="Offline", qos=0, retain=True)

        self.client.connect(self.server_address, 1883, 60)
        self.client.loop_start()


    def ping(self):
        self.slog("ping called")
        self.client.publish(path.join(self.tele_topic, "STATUS"), "Ping from victron2mqtt v0.1")


    def on_connect(self, client, userdata, flags, rc):
        self.client.publish(path.join(self.tele_topic, "LWT"), payload="Online", qos=0, retain=True)
        self.slog("Connect with result code " + str(rc))
        self.connected = True

    def on_message(self, client, userdata, msg):
        # (head, tail) = path.split(msg.topic)
       # parts = msg.topic.split("/")
       # item = parts[-1]

        self.stateCounter = self.stateCounter + 1
        # if(msg.topic.ends)

        self.slog(msg.topic + " " + str(msg.payload))


    def send_tele(self, statenum, stats):
        #msg = "CONNECTED {}" if connected else "NOT CONNECTED {}"
        self.client.publish(path.join(self.tele_topic, f"STATE{statenum}"), json.dumps(stats))

    def slog(self, msg):
        syslog.syslog(msg)
        print(msg)
