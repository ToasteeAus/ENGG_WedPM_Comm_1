#include <Arduino.h>
#include <WiFi.h>

/* wifi info */
#define ssid                   "" // Network Identifier
#define password               "" // Network Password

/* reconnection behaviour */
const int reconnectInterval = 500; // Time, in millis, to buffer waiting for connection to occur
const int reconnectAttemptMax = 10; // Maximum amount of reconnections before considering network completely dead
int currOutageTimer = 0; // Counter of retry attempts

void WiFiInit(){
  WiFi.begin(ssid, password);
}

bool IsWiFiAlive(){
  return WiFi.status() == WL_CONNECTED;
}

void WiFiWaitLoop(){
  Serial.print("\nConnecting");
  while(!IsWiFiAlive()){
    delay(reconnectInterval);
    currOutageTimer++;
    Serial.print(".");

    if(currOutageTimer == reconnectAttemptMax){
      Serial.println("\nFailed to re-establish Network connection. Terminating...");
      break;
    }
  }

  currOutageTimer = 0;
}

void BRWiFiSetup(){
  WiFiInit();
  WiFiWaitLoop();

  if (IsWiFiAlive()) {
    Serial.println("\nConnected to WiFi Network!");
    Serial.print("Connected @ ");
    Serial.print(WiFi.localIP().toString());
  } else {
    Serial.println("Check SSID, Password, and Network Health.");
  }
}

void BRWiFiHeartbeat(){
  if(!IsWiFiAlive()){
    BRWiFiSetup();
  }
}