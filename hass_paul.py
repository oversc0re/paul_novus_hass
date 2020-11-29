import paho.mqtt.client as mqtt
import yaml
import serial
import logging as log
import sys
import time
import threading
from mqtt import Hass_mqtt
from paul_decoder import Paul
config = yaml.safe_load(open("config.yaml"))
config_mqtt = config['mqtt']


log.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=log.INFO,
    datefmt='%S')

def paul_engine(mqtt_h):
    #s = serial.Serial('/dev/ttyUSB0', 9600, timeout=0.06, parity=serial.PARITY_NONE, rtscts=1 )
    status = {}
    port = 'com10'
    baud = 9600
    ser = serial.Serial(port, baudrate=baud, timeout=20
                        , stopbits=serial.STOPBITS_ONE,
                        parity=serial.PARITY_MARK,
                        bytesize=serial.EIGHTBITS
                        # rtscts=False,
                        # dsrdtr=False
                        )
    ser.set_buffer_size(rx_size = 12000, tx_size = 12000)
    buffer = ""
    state = "unsync"
    p = Paul(ser)
    while True:
        p.receive_frame()
        if status != p.status:
            status = p.status.copy()
            print(status)
            mqtt_h.mqtt.publish(config_mqtt['publish_topic'], str(status))
        time.sleep(0.0001)



# def check_gui_update():
# 	global q
# 	global text
# 	data = q.get()
# 	text.delete("0.0", tkinter.END)
# 	text.insert("0.0", data)
# 	root.after(200, check_gui_update)
#

mqtt = Hass_mqtt(config_mqtt)

x = threading.Thread(target=paul_engine, args=(mqtt,))
x.start()

mqtt.mqtt.loop_start()
