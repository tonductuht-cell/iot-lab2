import json
import random
import time
import paho.mqtt.client as mqtt
from common import HOST, PORT
if __name__ == '__main__':
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect(HOST,PORT,60)
    c.loop_start()
    seq = 0
    try:
        while True:
            seq += 1
            data = dict(device_id='sim01',ts_ms=int(time.time()*1000),seq=seq,
                        temperature=round(random.gauss(28,0.4),2),
                        humidity=round(random.gauss(65,1),2))
            if seq % 25 == 0: data['temperature'] = 65.0
            if seq % 17 == 0: data['humidity'] = None
            c.publish('iot/lab2/sim01/telemetry',json.dumps(data),qos=1).wait_for_publish()
            print(data,flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        c.disconnect()
        c.loop_stop()
