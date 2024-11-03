#include <WiFi.h>
#include <Wire.h>

// WiFi credentials
const char* ssid     = "AndroidAFB94"; // Replace with LAN name and pass
const char* password = "Test1234";

// Server address and port
const char* ccpIP = "192.168.57.177";  // Replace with the IP address of your local python server
const uint16_t ccpPort = 3028;

// WiFi/Client status ints
int wifiReconnecting = 0;
int ccpReconnecting = 0;
bool disconnected = false;

WiFiClient client;

void wifiEventListener(WiFiEvent_t event){
  switch (event) {
      case ARDUINO_EVENT_WIFI_READY: 
          Serial.println("WiFi: Interface ready");
          break;
      case ARDUINO_EVENT_WIFI_STA_CONNECTED:
          Serial.println("WiFi: Connected to ENGG2K3K Network");
          break;
      case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
          Serial.println("WiFi: Disconnected from ENGG2K3K Network, Attempting to reconnect\n");
          WiFi.begin(ssid, password);
          break;
      case ARDUINO_EVENT_WIFI_STA_GOT_IP:
          Serial.print("WiFi: Received IP Address: ");
          Serial.println(WiFi.localIP());
          break;
      default: break;
  }
}

void reconnectWifi(){
  wifiReconnecting = 1;
  WiFi.begin(ssid, password);
  Serial.println("WiFi: Connecting");

  while(!WiFi.isConnected()){}

  wifiReconnecting = 0;
}

void setupWifi(){
  WiFi.disconnect(true); // Turn off and clear from last instance
  delay(500);
  WiFi.onEvent(wifiEventListener);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  reconnectWifi();
}

void setupCCP(){
  ccpReconnecting = 1;
  Serial.print("CCP: Connecting");
  while(!client.connected() && WiFi.isConnected()){
    try{
      client.connect(ccpIP, ccpPort, 250);
    } catch (...){}
  }
  
  // Logic purely here for the case where WiFi drops before we can contact the CCP
  if(WiFi.isConnected()){
    Serial.println("\nCCP: Connected");
  } else {
    reconnectWifi();
  }
  
  ccpReconnecting = 0;
}

void sendAckToCCP(uint8_t byteCode){
  uint8_t hexAckData[] = {0xAA, byteCode};

  client.write(hexAckData, sizeof(hexAckData));

  Serial.printf("ESP: Sent ACK to CCP Server: 0x%02X\n", byteCode);
}

void sendAlertToCCP(uint8_t alertCode){
  uint8_t hexAlertData[] = {0xFF, alertCode};

  client.write(hexAlertData, sizeof(hexAlertData));

  Serial.printf("ESP: Sent ALERT to CCP Server: 0x%02X\n", alertCode);
}

void decipherCCPCommand(){
  if(client.connected() and client.available()){
    uint8_t data = client.read();  // Read a byte

    switch(data){
      case 0:
        Serial.println("Received Stop Command");
        break;
      case 1:
        Serial.println("Received Forward Slow Command");
        break;
      case 2:
        Serial.println("Received Forward Fast Command");
        break;
      case 3:
        Serial.println("Received Reverse Slow Command");
        break;
      case 4:
        Serial.println("Received Reverse Fast Command");
        break;
      case 5:
        Serial.println("Received Doors Open Command");
        break;
      case 6:
        Serial.println("Received Doors Close Command");
        break;
      case 0xFF:
        Serial.println("Received Disconnect Command");
        break;
      default:
        Serial.printf("Unknown ByteCode: 0x%02X\n", data);
        break;
    }

    if (data >= 0 && data <= 8){
      sendAckToCCP(data);
    }
  }
  
  if(!client.connected() and disconnected == false){
    setupCCP();
  }
}

void setup() {
  Serial.begin(115200);
  setupWifi();

  while(!WiFi.isConnected()){} // Blocking wait for WiFi before attempting CCP connection
  setupCCP();
}

void loop() {
  if (disconnected == false){
    if (wifiReconnecting == 0 and ccpReconnecting == 0){
      // Execute Commands Received
      decipherCCPCommand();
    }
  }
}