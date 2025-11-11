/********* ESP32 — Firebase RTDB (Anonymous auth) *********
 * Sensors: DHT22 on GPIO14, Soil analog on GPIO32
 * DB paths: /nodes/<UID>/latest and /nodes/<UID>/history
 **********************************************************/
#include <Arduino.h>
#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include "addons/TokenHelper.h"
#include "addons/RTDBHelper.h"
#include "DHT.h"

/******** WiFi ********/
#define WIFI_SSID       "Magic Castle"
#define WIFI_PASSWORD   "2405Magic"

/******** Firebase ********/
#define API_KEY         "AIzaSyDqTLpAsXbslKYv5Oh6n5IzNzigbPWFANY"
#define DATABASE_URL    "https://giatest-74d4a-default-rtdb.firebaseio.com" // https://...rtdb.<region>.firebasedatabase.app

// (Keep these for later if you switch to email/password auth)
// #define USER_EMAIL      "node01@yourproj.dev"
// #define USER_PASSWORD   "VeryStrong!Passw0rd"

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

/******** Sensors ********/
#define DHTPIN    14
#define DHTTYPE   DHT22
#define SOIL_PIN  32
DHT dht(DHTPIN, DHTTYPE);

// Soil calibration
const int SOIL_DRY = 2700;  // 0%
const int SOIL_WET = 1000;  // 100%
const int NUM_SAMPLES = 10;

String myUID;
unsigned long lastSend = 0;
const unsigned long SEND_EVERY_MS = 5000;

int soilAverage() {
  long sum = 0;
  for (int i=0;i<NUM_SAMPLES;i++){ sum += analogRead(SOIL_PIN); delay(10); }
  return sum / NUM_SAMPLES;
}
int soilToPct(int raw){
  int pct = map(raw, SOIL_DRY, SOIL_WET, 0, 100);
  return constrain(pct, 0, 100);
}

void wifiConnect(){
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED){ Serial.print("."); delay(300); }
  Serial.printf("\nWi-Fi OK: %s\n", WiFi.localIP().toString().c_str());
}

void firebaseInit(){
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;

  // ---------- Anonymous sign-up (DEV-friendly) ----------
  if (Firebase.signUp(&config, &auth, "", "")) {
    Serial.println("[FB] Anonymous signup OK");
  } else {
    Serial.printf("[FB] signup error: %s\n", config.signer.signupError.message.c_str());
  }

  // ---------- (Keep for later: email/password device auth) ----------
  // auth.user.email = USER_EMAIL;
  // auth.user.password = USER_PASSWORD;

  config.token_status_callback = tokenStatusCallback;
  config.max_token_generation_retry = 5;

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  // Wait briefly for UID
  Serial.print("[FB] Waiting for UID");
  unsigned long t0 = millis();
  while (auth.token.uid == "" && millis() - t0 < 10000) { Serial.print("."); delay(250); }
  myUID = auth.token.uid.c_str();
  Serial.printf("\n[FB] UID: %s\n", myUID.length() ? myUID.c_str() : "(none)");
}

void setup(){
  Serial.begin(115200);
  delay(200);
  Serial.println("\n🌱 ESP32 Anonymous RTDB Node");

  dht.begin();
  pinMode(SOIL_PIN, INPUT);

  wifiConnect();
  firebaseInit();
}

void loop(){
  if (millis() - lastSend < SEND_EVERY_MS) return;
  lastSend = millis();

  float hum = dht.readHumidity();
  float tC  = dht.readTemperature(); // °C
  if (isnan(hum) || isnan(tC)) {
    Serial.println("❌ DHT read failed; skipping");
    return;
  }
  float tF     = tC * 1.8f + 32.0f;  // keep °F to match your UI
  int   raw    = soilAverage();
  int   soilPc = soilToPct(raw);
  int   lux    = 15000 + random(-1200, 1200); // placeholder if no lux sensor
  long  ts     = time(NULL);

  Serial.printf("→ hum=%.1f%% temp=%.1f°F soil=%d%% lux=%d raw=%d\n", hum, tF, soilPc, lux, raw);

  // Guard if UID didn’t populate yet
  String base = myUID.length() ? ("nodes/" + myUID) : "nodes/_anon";

  // latest
  FirebaseJson latest;
  latest.set("hum", hum);
  latest.set("temp", tF);
  latest.set("soil", soilPc);
  latest.set("light", lux);
  latest.set("ts", (int)ts);

  if (Firebase.RTDB.setJSON(&fbdo, base + "/latest", &latest)) {
    Serial.println("[FB] latest OK");
  } else {
    Serial.printf("[FB] latest ERR: %s\n", fbdo.errorReason().c_str());
  }

  // history (append)
  FirebaseJson hist = latest;
  if (Firebase.RTDB.pushJSON(&fbdo, base + "/history", &hist)) {
    Serial.println("[FB] history OK");
  } else {
    Serial.printf("[FB] history ERR: %s\n", fbdo.errorReason().c_str());
  }

  // Keep token fresh
  if (Firebase.isTokenExpired()) {
    Firebase.refreshToken(&config);
    Serial.println("[FB] token refreshed");
  }
}
