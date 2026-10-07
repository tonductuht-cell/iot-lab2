import pandas as pd
import streamlit as st
from common import db, read_data
st.set_page_config(page_title='IoT Lab 2',layout='wide')
st.title('Giám sát nhiệt độ và độ ẩm')
minutes = st.sidebar.slider('Khoảng thời gian (phút)',1,120,30)
@st.fragment(run_every='5s')
def live():
    try:
        with db() as c:
            raw = read_data(c,'sensor_raw',minutes)
            clean = read_data(c,'sensor_clean',minutes)
        if raw.empty:
            st.info('Chưa có dữ liệu. Chạy collector và simulator hoặc ESP32.'); return
        device = st.selectbox('Thiết bị',sorted(raw.device_id.unique()))
        raw = raw[raw.device_id == device].sort_values('_time')
        a,b,c = st.columns(3)
        a.metric('Số bản tin lưu được',len(raw))
        latency = raw['latency_ms'].dropna()
        b.metric('Độ trễ trung bình tới collector',f'{latency.mean():.1f} ms')
        c.metric('P95 độ trễ tới collector',f'{latency.quantile(.95):.1f} ms')
        st.caption('Độ trễ = thời điểm collector nhận − timestamp thiết bị. Cần đồng bộ đồng hồ; chưa gồm thời gian ghi DB và refresh dashboard.')
        gap = raw.seq.diff()
        st.write('Khoảng trống seq quan sát được:',int((gap[gap>1]-1).sum()),
                 '— ước lượng, cần đối chiếu nhật ký thiết bị khi có bản tin đến muộn hoặc khởi động lại.')
        st.subheader('Dữ liệu thô')
        st.line_chart(raw.set_index('_time').reindex(columns=['temperature','humidity']))
        if not clean.empty:
            clean = clean[clean.device_id == device].sort_values('_time').copy()
            for col in list(clean.columns):
                if col.endswith('_valid') and col[:-6] in clean:
                    clean.loc[~clean[col].fillna(False).astype(bool),col[:-6]] = float('nan')
            st.subheader('Dữ liệu sau xử lý mỗi 10 giây')
            st.line_chart(clean.set_index('_time').reindex(columns=['temperature','temperature_rolling_mean','humidity']))
            st.dataframe(clean.tail(30),hide_index=True)
        st.download_button('Tải dữ liệu thô CSV',raw.to_csv(index=False).encode(),file_name='raw.csv')
    except Exception as e:
        st.error(f'Không đọc được database: {e}')
live()
