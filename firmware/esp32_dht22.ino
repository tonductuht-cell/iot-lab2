#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <time.h>
#include <sys/time.h>
const char* SSID = "YOUR_WIFI";
const char* PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_HOST = "192.168.1.10"; // IP LAN của máy chạy Docker
const char* DEVICE = "esp32-01";
const char* TOPIC = "iot/lab2/esp32-01/telemetry";
DHT dht(4, DHT22);
WiFiClient net;
PubSubClient mqtt(net);
uint32_t seq = 0;
unsigned long lastSend = 0, lastConnect = 0;
void setup() {
  Serial.begin(115200);
  dht.begin();
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  while (time(nullptr) < 1700000000) { delay(500); }
  mqtt.setServer(MQTT_HOST, 1883);
  mqtt.setBufferSize(512);
}
void loop() {
  if (WiFi.status() != WL_CONNECTED) { delay(100); return; }
  if (!mqtt.connected() && millis()-lastConnect >= 3000) {
    lastConnect = millis();
    mqtt.connect(DEVICE);
  }
  mqtt.loop();
  if (!mqtt.connected() || millis()-lastSend < 2000) return;
  lastSend = millis();
  float t = dht.readTemperature(), h = dht.readHumidity();
  if (isnan(t) || isnan(h)) { Serial.println("DHT read failed"); return; }
  timeval tv;
  gettimeofday(&tv, nullptr);
  long long ts = (long long)tv.tv_sec*1000 + tv.tv_usec/1000;
  char payload[256];
  snprintf(payload,sizeof(payload),
    "{\"device_id\":\"%s\",\"ts_ms\":%lld,\"seq\":%lu,\"temperature\":%.2f,\"humidity\":%.2f}",
    DEVICE,ts,(unsigned long)++seq,t,h);
  bool ok = mqtt.publish(TOPIC,payload,false);
  Serial.printf("publish=%d %s\n",ok,payload);
}
