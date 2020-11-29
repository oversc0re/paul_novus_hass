import paho.mqtt.client as mqtt
import yaml
import serial
from paul_decoder import Paul
config = yaml.safe_load(open("config.yaml"))
config_mqtt = config['mqtt']

class Hass_mqtt:
    def __init__(self, config_mqtt):
        self.config_mqtt = config_mqtt
        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.mqtt.connect(self.config_mqtt['server'], self.config_mqtt['port'], self.config_mqtt['keepalive'])

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        #self.mqtt.loop_forever()

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(client, userdata, flags, rc):
        print("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(self.config_mqtt['subscribe_topic'])

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        print(msg.topic+" "+str(msg.payload))
