"""Durable local outbox; acknowledge MQTT only after SQLite commit."""
import json
import logging
import sqlite3
import threading
import time
import paho.mqtt.client as mqtt
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from common import db, HOST, PORT, BUCKET, ORG
from validation import validate
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

def connection():
    c = sqlite3.connect('outbox.db', timeout=30)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=FULL')
    c.execute('''CREATE TABLE IF NOT EXISTS events
      (device TEXT, ts INTEGER, payload TEXT, received INTEGER, sent INTEGER DEFAULT 0,
       PRIMARY KEY(device, ts))''')
    c.commit()
    return c

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe('iot/lab2/+/telemetry', qos=1)
        logging.info('MQTT connected')
    else:
        logging.error('MQTT refused: %s', reason_code)

def on_message(client, userdata, msg):
    try:
        if len(msg.payload) > 4096:
            raise ValueError('payload too large')
        data = validate(json.loads(msg.payload), msg.topic)
    except (ValueError, UnicodeDecodeError) as e:
        logging.warning('Rejected: %s', e)
        if msg.qos: client.ack(msg.mid, msg.qos)
        return
    try:
        with connection() as c:
            c.execute('INSERT OR IGNORE INTO events(device,ts,payload,received) VALUES(?,?,?,?)',
                      (data['device_id'],data['ts_ms'],json.dumps(data),int(time.time()*1000)))
        if msg.qos: client.ack(msg.mid, msg.qos)
    except sqlite3.Error:
        logging.exception('Local storage failed; MQTT not acknowledged')
        client.disconnect()

def writer():
    with db() as influx, connection() as c:
        api = influx.write_api(write_options=SYNCHRONOUS)
        while True:
            rows = c.execute('SELECT device,ts,payload,received FROM events WHERE sent=0 LIMIT 100').fetchall()
            for device, ts, payload, received in rows:
                data = json.loads(payload)
                p = Point('sensor_raw').tag('device_id',device).time(ts,WritePrecision.MS)
                for field in ('temperature','humidity'):
                    if field in data: p.field(field,data[field])
                p.field('seq',data['seq']).field('received_ms',received).field('latency_ms',float(received-ts))
                try:
                    api.write(bucket=BUCKET,org=ORG,record=p)
                    c.execute('UPDATE events SET sent=1 WHERE device=? AND ts=?',(device,ts))
                    c.commit()
                except Exception:
                    logging.exception('InfluxDB write failed; retry in 3 seconds')
                    time.sleep(3)
                    break
            # Keep dedup keys for the same 24h accepted timestamp window.
            c.execute('DELETE FROM events WHERE sent=1 AND ts < ?', (int(time.time()*1000)-86400000,))
            c.commit()
            time.sleep(0.5)

if __name__ == '__main__':
    connection().close()
    threading.Thread(target=writer,daemon=True).start()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='lab2-collector',
                         clean_session=False,manual_ack=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(1,30)
    client.connect(HOST,PORT,60)
    client.loop_forever(retry_first_connection=True)
