from __future__ import annotations

import sys
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

host, port, username, password, topic = sys.argv[1:]
client = mqtt.Client(CallbackAPIVersion.VERSION2)
client.username_pw_set(username, password)
client.will_set(topic, b"offline", qos=1, retain=True)
client.connect(host, int(port), keepalive=2)
client.loop_start()
while not client.is_connected():
    time.sleep(0.01)
print("ready", flush=True)
time.sleep(60)
