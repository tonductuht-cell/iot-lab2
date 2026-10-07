# Bài thực hành số 2 Thu thập lưu trữ và tiền xử lý dữ liệu IoT

Bộ source cho ESP32 + DHT22, Mosquitto, InfluxDB 2.7 và Streamlit.
Có simulator để demo không cần board. Python 3.11 hoặc 3.12 và Docker Compose v2.

## 1. Kiến trúc

ESP32 hoặc simulator → MQTT topic iot/lab2/<device_id>/telemetry → collector
→ SQLite outbox → InfluxDB sensor_raw → preprocess → sensor_clean → dashboard.
Dashboard đọc cả sensor_raw và sensor_clean mỗi 5 giây.

## 2. Cài và chạy không cần phần cứng

Giải nén, mở terminal trong thư mục iot-lab2.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
```

Windows PowerShell: dùng `Copy-Item .env.example .env`, `python -m venv .venv`,
`.venv\Scripts\Activate.ps1`; các lệnh còn lại giống nhau.
Mỗi terminal mới cần kích hoạt .venv và đứng trong thư mục dự án.
Đợi InfluxDB hoàn tất khởi tạo; vào http://localhost:8086, tài khoản admin,
mật khẩu lấy từ INFLUX_PASSWORD trong .env. Không thay cấu hình .env sau khi DB
đã khởi tạo mà không cập nhật cấu hình tương ứng trong DB.

Terminal 1:
```bash
python collector.py
```
Terminal 2:
```bash
python simulator.py
```
Terminal 3:
```bash
python preprocess.py --watch --minutes 60
```
Terminal 4:
```bash
streamlit run dashboard.py
```
Mở http://localhost:8501. Đợi 30–60 giây để có cửa sổ xử lý hoàn chỉnh.
Simulator gửi mỗi 2 giây, tạo nhiệt độ bất thường mỗi 25 bản tin và thiếu độ ẩm
mỗi 17 bản tin. Đây là dữ liệu giả lập, cần ghi rõ trong báo cáo.

Dừng bằng Ctrl+C và `docker compose stop`. Khởi động lại bằng `docker compose up -d`.
Không dùng `docker compose down -v` nếu cần giữ số liệu, vì lệnh đó xóa volumes.

## 3. Chạy ESP32 thật

Nối DHT22 VCC → 3V3, GND → GND, DATA → GPIO4. Cảm biến rời cần điện trở kéo lên
4.7–10 kΩ giữa DATA và 3V3; module thường đã có. Đối chiếu chân trên module.
Arduino IDE: cài board ESP32 by Espressif Systems, thư viện DHT sensor library
by Adafruit, Adafruit Unified Sensor và PubSubClient by Nick O'Leary.
Mở firmware/esp32_dht22.ino, sửa SSID, PASSWORD, MQTT_HOST thành IP LAN máy tính.
Chọn board và cổng serial, upload; Serial Monitor 115200.
ESP32 và máy tính cùng mạng, firewall cho phép TCP 1883. ESP32 dùng IP máy tính,
không dùng localhost. Internet/NTP cần hoạt động để timestamp hợp lệ.
Nếu thay DEVICE, phải thay TOPIC tương ứng. Có thể dừng simulator hoặc chạy cả hai.

PubSubClient publish QoS 0: có thể mất bản tin khi mất mạng, không có hàng đợi
trên ESP32. Subscribe QoS 1 không nâng QoS của publisher. Simulator publish QoS 1.
Nếu cần bảo đảm hơn, dùng firmware có QoS 1 và lưu đệm trên thiết bị.

## 4. JSON và schema

```json
{"device_id":"esp32-01","ts_ms":1791352800000,"seq":1,"temperature":28.5,"humidity":65.2}
```
Timestamp minh họa; khi gửi thật phải lấy thời gian hiện tại UTC epoch milliseconds.
Collector kiểm tra topic khớp device, số hữu hạn, nhiệt độ -40..80°C, độ ẩm 0..100%,
seq nguyên không âm, timestamp không cũ quá 24h hoặc vượt tương lai quá 60s.
Cho phép một cảm biến thiếu/null; không chấp nhận cả hai thiếu.

| Measurement | Tag | Timestamp | Fields |
|---|---|---|---|
| sensor_raw | device_id | thời gian thiết bị | temperature, humidity, seq, received_ms, latency_ms |
| sensor_clean | device_id | đầu cửa sổ UTC 10s | giá trị xử lý, rolling mean, delta, norm, sample_count, outlier_count, missing và valid flags |

Một bucket iot retention 30 ngày cho cả hai measurement. Muốn giữ dữ liệu xử lý
lâu hơn: tạo bucket khác với retention riêng và đổi nơi ghi/đọc sensor_clean.
Không dùng seq hoặc timestamp làm tag vì tăng cardinality.
Trùng được định nghĩa bởi device_id + ts_ms; các lần ghi lại cùng khóa có tính
idempotent. Thiết bị phải tạo timestamp khác nhau cho mỗi mẫu, kể cả sau reboot.
SQLite commit trước MQTT ACK cho QoS 1; InfluxDB lỗi thì giữ hàng đợi, thử lại.
SQLite chỉ giữ khóa đã ghi 24h; bản tin cũ hơn bị từ chối. Khi DB hỏng kéo dài,
outbox có thể tăng và đầy đĩa: theo dõi dung lượng, chưa có cơ chế giới hạn/backpressure.
Không chạy hai collector có cùng client_id hoặc cùng file outbox.

## 5. Tiền xử lý

Mỗi thiết bị xử lý riêng: sắp xếp, bỏ trùng timestamp; IQR theo khoảng truy vấn
(q1-1.5*IQR, q3+1.5*IQR), chỉ dùng khi có ít nhất 8 giá trị và IQR > 0;
đổi outlier thành NaN. Lấy trung bình cửa sổ 10s; điền tiến tối đa 2 cửa sổ
thiếu (20 giây), khoảng thiếu dài hơn còn NaN; không điền ngược từ tương lai.
Rolling mean 3 cửa sổ (30 giây), delta so với cửa sổ trước.
Chuẩn hóa min-max theo khoảng vật lý cố định: nhiệt độ (x+40)/120, độ ẩm x/100.
Chỉ lưu cửa sổ đã kết thúc. Các giá trị thiếu lưu placeholder 0 kèm *_valid=false;
dashboard che placeholder, tuyệt đối không coi 0 đó là số đo.

IQR tính trên toàn khoảng truy vấn, nên kết quả có thể thay đổi khi chạy lại
hoặc khi khoảng truy vấn trượt. Cửa sổ đầu khoảng truy vấn có thể thiếu mẫu.
Đây là xử lý batch cho thực hành, không phải phát hiện bất thường nhân quả hoàn chỉnh.
Để đánh giá cố định, chọn khoảng thực nghiệm, giữ bản CSV và ghi rõ tham số.

## 6. Demo và số liệu cho báo cáo 4–6 trang

1. Chạy giả lập 5–10 phút, chụp dashboard thô/clean và bảng đặc trưng.
2. Ghi số bản tin, khoảng trống seq, mean/P95 latency trên dashboard, dung lượng
   outbox.db và volume InfluxDB, số thiết bị và chu kỳ publish.
3. `docker compose stop influxdb`, cho gửi thêm 30s; xem collector báo retry.
   `docker compose start influxdb`, kiểm tra hàng đợi ghi tiếp.
4. Gửi lại chính xác một JSON cùng device và ts; kiểm tra không thêm điểm trùng.
5. Kiểm tra nhiệt độ 65°C từ simulator bị IQR loại khi có đủ mẫu bình thường;
   độ ẩm null được xử lý theo cửa sổ, missing flag phản ánh thiếu trung bình sau resample.

Latency dashboard = received_ms − ts_ms: đo tới collector, KHÔNG phải toàn bộ
end-to-end. Đồng bộ NTP máy tính/ESP32; giá trị âm có thể do lệch đồng hồ.
Để đo đến DB: trên máy collector đo elapsed bằng time.perf_counter() quanh
api.write (thời gian ghi), đồng thời ghi thời điểm write trả về thành CSV,
tính write_return_epoch_ms − ts_ms (độ trễ đến khi DB xác nhận).
Đến dashboard: lưu thời điểm mẫu xuất hiện trên UI trừ ts_ms, ghi nhận refresh 5s;
không cộng P95 của các thành phần để suy ra P95 toàn pipeline.
Seq gap chỉ là ước lượng khi bản tin đến muộn/reset; so với nhật ký publish thực tế
để tính mất mát. Firmware QoS0 không chứng minh được không mất dữ liệu.

Bố cục báo cáo: (1) mục tiêu + kiến trúc; (2) kết nối + schema + retention;
(3) các bước tiền xử lý; (4) ảnh và bảng số liệu thực nghiệm;
(5) phân tích độ trễ, lưu trữ, hạn chế, cải tiến, khó khăn.
Không bịa số liệu: điền kết quả chạy trên máy bạn. Cải tiến: MQTT TLS/auth,
QoS1 + buffer firmware, batch write, retention riêng và giám sát disk/cardinality.
Broker anonymous chỉ phục vụ lab mạng nội bộ; không mở cổng ra Internet.

## 7. Lỗi thường gặp

- Connection refused: kiểm tra Docker đang chạy, `docker compose logs mqtt influxdb`.
- 401 Unauthorized: token/org/bucket phải khớp thiết lập DB ban đầu.
- Không có clean: chạy preprocess, đợi cửa sổ đóng, kiểm tra dữ liệu thô.
- Timestamp rejected: kiểm tra NTP, không dùng uptime millis() thay epoch.
- Không đọc DHT: kiểm tra nguồn, GPIO, pull-up, đúng DHT22 và chu kỳ >=2s.
- Port occupied: đóng dịch vụ đang chiếm 1883/8086/8501 hoặc chỉnh mapping phù hợp.

## 8. Nộp source lên GitHub

Tạo repository mới trên GitHub rồi chạy (thay URL bằng repository của bạn):
```bash
git init
git add .
git commit -m "Complete IoT lab 2 pipeline"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/iot-lab2.git
git push -u origin main
```
.env và database đã được bỏ qua bằng .gitignore. Không đưa mật khẩu Wi-Fi thật
trong firmware lên GitHub; thay bằng placeholder trước khi commit.

## 9. Kiểm tra đã thực hiện với bộ source

Đã kiểm tra cú pháp Python và kiểm tra cục bộ validation/processing bằng dữ liệu
có trùng, null và outlier. Chưa chạy tích hợp MQTT/InfluxDB/Streamlit hoặc biên dịch
firmware trong môi trường tạo source; cần thực hiện các bước demo ở trên trên máy bạn.
