import argparse
import time
import pandas as pd
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from common import db, read_data, BUCKET, ORG
from processing import process_device

def run(minutes):
    with db() as c:
        frame = read_data(c,'sensor_raw',minutes)
        if frame.empty:
            print('Chua co du lieu'); return
        points = []
        for device,group in frame.groupby('device_id'):
            for timestamp,row in process_device(group).iterrows():
                p = Point('sensor_clean').tag('device_id',device).time(timestamp.to_pydatetime(),WritePrecision.NS)
                for name,value in row.items():
                    # Write a validity flag and numeric placeholder so reruns cannot
                    # leave old Influx fields behind when a value becomes missing.
                    if name.endswith('_missing'):
                        p.field(name,bool(value))
                    else:
                        valid = bool(pd.notna(value))
                        p.field(name+'_valid',valid).field(name,float(value) if valid else 0.0)
                points.append(p)
        if points:
            c.write_api(write_options=SYNCHRONOUS).write(bucket=BUCKET,org=ORG,record=points)
        print(f'Written {len(points)} cleaned windows')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--minutes',type=int,default=60)
    parser.add_argument('--watch',action='store_true')
    args = parser.parse_args()
    while True:
        try: run(args.minutes)
        except Exception as e:
            if not args.watch: raise
            print(f'Retry: {e}')
        if not args.watch: break
        time.sleep(10)
