import os
import json
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
import pandas as pd
load_dotenv()
ORG = os.getenv('INFLUX_ORG', 'iot-lab')
BUCKET = os.getenv('INFLUX_BUCKET', 'iot')
HOST = os.getenv('MQTT_HOST', 'localhost')
PORT = int(os.getenv('MQTT_PORT', '1883'))

def db():
    return InfluxDBClient(url=os.getenv('INFLUX_URL', 'http://localhost:8086'),
                          token=os.environ['INFLUX_TOKEN'], org=ORG, timeout=10000)

def read_data(client, measurement, minutes=60):
    minutes = int(minutes)
    if not 1 <= minutes <= 43200:
        raise ValueError('minutes must be 1..43200')
    query = f'''from(bucket: {json.dumps(BUCKET)})
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == {json.dumps(measurement)})
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'''
    frames = client.query_api().query_data_frame(query, org=ORG)
    if isinstance(frames, list):
        frames = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return frames
