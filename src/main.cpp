#include <Arduino.h>
#include "BRWiFiModule.h"

void setup() {
  Serial.begin(115200);

  BRWiFiSetup();
}

void loop() {
  delay(1000);
  Serial.println("ESP32 is alive");
  BRWiFiHeartbeat();
}