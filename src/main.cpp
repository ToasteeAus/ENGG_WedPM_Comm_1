#include <Arduino.h>
#include <brwifi.h>

void setup() {
  Serial.begin(115200);
  delay(1000); // Only required to ensure the Serial Monitor is initialised before we start pumping it with info
  xTaskCreatePinnedToCore(init_wifi, "WiFiSetup", 10240, NULL, 3, NULL, 0);
  delay(10);
}

void loop() {
  delay(1000);
  Serial.println(heartbeat());
}

