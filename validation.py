import math
import re
import time

def validate(data, topic, now=None):
    if not isinstance(data, dict):
        raise ValueError('JSON must be an object')
    device = data.get('device_id')
    if not isinstance(device, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', device):
        raise ValueError('invalid device_id')
    if topic != f'iot/lab2/{device}/telemetry':
        raise ValueError('topic/device mismatch')
    for name in ('ts_ms', 'seq'):
        value = data.get(name)
        if type(value) is not int or value < 0:
            raise ValueError(f'invalid {name}')
    now = time.time() * 1000 if now is None else now
    if not now - 86400000 <= data['ts_ms'] <= now + 60000:
        raise ValueError('timestamp outside accepted range; synchronize clock')
    limits = {'temperature': (-40,80), 'humidity': (0,100)}
    result = {k:data[k] for k in ('device_id','ts_ms','seq')}
    for name, (low, high) in limits.items():
        value = data.get(name)
        if value is None:
            continue
        if type(value) not in (float,int) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'invalid {name}')
        result[name] = float(value)
    if not any(k in result for k in limits):
        raise ValueError('no sensor reading')
    return result
