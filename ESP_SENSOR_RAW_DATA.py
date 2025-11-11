#include "DHT.h"

#define DHTPIN 14
#define DHTTYPE DHT22
#define SOIL_PIN 32

DHT dht(DHTPIN, DHTTYPE);

// --- Calibration values from your tests ---
const int SOIL_DRY = 2700;  // Raw reading = 0% moisture
const int SOIL_WET = 1000;  // Raw reading = 100% moisture

const int NUM_SAMPLES = 10; // For averaging

int getSoilAverage() {
  long sum = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    sum += analogRead(SOIL_PIN);
    delay(10); // Small delay for stability
  }
  return sum / NUM_SAMPLES;
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("🌱 Calibrated DHT22 + Soil Moisture Meter Ready");
}

void loop() {
  float humidity = dht.readHumidity();
  float temperatureC = dht.readTemperature();
  float temperatureF = temperatureC * 1.8 + 32;

  int rawSoil = getSoilAverage();

  // --- Inverted map based on calibration ---
  int moisturePercent = map(rawSoil, SOIL_DRY, SOIL_WET, 0, 100);
  moisturePercent = constrain(moisturePercent, 0, 100);

  // --- Soil condition ---
  String soilStatus;
  if (moisturePercent >= 70) soilStatus = "Wet";
  else if (moisturePercent <= 30) soilStatus = "Dry";
  else soilStatus = "Moderate";

  // --- Output ---
  if (isnan(humidity) || isnan(temperatureC)) {
    Serial.println("❌ Failed to read from DHT22 sensor!");
  } else {
    Serial.print("Temp: "); Serial.print(temperatureC); Serial.print(" °C / ");
    Serial.print(temperatureF); Serial.print(" °F | Humidity: ");
    Serial.print(humidity); Serial.print("% | Soil Value: ");
    Serial.print(rawSoil); Serial.print(" (");
    Serial.print(moisturePercent); Serial.print("%) → ");
    Serial.println(soilStatus);
  }

  delay(2000);
}
