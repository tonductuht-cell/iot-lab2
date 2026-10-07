import pandas as pd
import numpy as np
FIELDS = ['temperature','humidity']

def process_device(frame):
    frame = frame.copy()
    frame['_time'] = pd.to_datetime(frame['_time'],utc=True)
    frame = frame.sort_values('_time').drop_duplicates('_time').set_index('_time')
    data = frame.reindex(columns=FIELDS).apply(pd.to_numeric, errors='coerce')
    flags = pd.DataFrame(False,index=data.index,columns=FIELDS)
    for field in FIELDS:
        s = data[field].dropna()
        if len(s) >= 8:
            q1,q3 = s.quantile([0.25,0.75])
            iqr = q3-q1
            if iqr > 0:
                flags[field] = (data[field] < q1-1.5*iqr) | (data[field] > q3+1.5*iqr)
                data.loc[flags[field],field] = np.nan
    out = data.resample('10s').mean()
    out['sample_count'] = data.resample('10s').size()
    out['outlier_count'] = flags.sum(axis=1).resample('10s').sum()
    for field in FIELDS:
        out[field+'_missing'] = out[field].isna()
        # Fill at most 2 bins, forward only; larger gaps remain missing.
        out[field] = out[field].ffill(limit=2)
        out[field+'_rolling_mean'] = out[field].rolling(3,min_periods=1).mean()
        out[field+'_delta'] = out[field].diff()
        # Fixed physical ranges make repeated runs comparable.
        low,high = (-40,80) if field == 'temperature' else (0,100)
        out[field+'_norm'] = (out[field]-low)/(high-low)
    # The final open bin changes; write only completed bins.
    end = pd.Timestamp.now(tz='UTC').floor('10s')
    return out[out.index < end]
