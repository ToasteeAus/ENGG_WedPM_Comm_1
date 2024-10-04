#include <WiFi.h>
#include <ESP32Servo.h>
#include <Adafruit_NeoPixel.h>

/*
  CRITICAL NOTE: DO NOT SEND PRINTLN COMMANDS TO PYTHON SERVER, IT HAS A FIT <3
*/

// Pin definitions
#define DIS_PIN 15
#define DIR_PIN 13
#define PWM_PIN 12

#define R_DOOR_PIN 23
#define L_DOOR_PIN 27
#define R_DOOR_SENSE_PIN 35
#define L_DOOR_SENSE_PIN 34

#define PIN_NEO_PIXEL 4

// Status LEDs
#define NUM_PIXELS 4    // The number of LEDs in sequence

// WiFi credentials
const char* ssid     = "AndroidAFB94"; // Replace with LAN name and pass
const char* password = "Test1234";

// WiFi/Client status ints
int wifiReconnecting = 0;
int ccpReconnecting = 0;

// // Static IP configuration
// IPAddress staticIP(10, 20, 30, 128); // ESP32 static IP
// IPAddress gateway(10, 20, 30, 250);    // IP Address of your network gateway (router)
// IPAddress subnet(255, 255, 255, 0);   // Subnet mask
// IPAddress primaryDNS(10, 20, 30, 1); // Primary DNS (optional)
// IPAddress secondaryDNS(0, 0, 0, 0);   // Secondary DNS (optional)

// Server address and port
const char* ccpIP = "192.168.234.177";  // Replace with the IP address of your local python server
const uint16_t ccpPort = 3028;

// Station and Motor Speeds
int fast_speed = 255;
int slow_speed = 150;
int atStation = 0;

// Class Object Constructors
Adafruit_NeoPixel NeoPixel(NUM_PIXELS, PIN_NEO_PIXEL, NEO_GRB + NEO_KHZ800);
WiFiClient client;
Servo leftdoor;
Servo rightdoor;

// 0x00 - STOP, 0x01 - FORWARD, SLOW, 0x02 - FORWARD, FAST, 0x03 - REVERSE, SLOW, 
// 0x04 - REVERSE, FAST, 0x05 - DOORS, OPEN, 0x06 - DOORS, CLOSE

// Custom Byte Codes
// 0x07 - SetSlowSpeed ex. 0x07 0xFF -> Slow Speed set to 255
// 0x08 - SetFastSpeed ex 0x08 0xFF -> Fast Speed set to 255

// Custom Byte Code Variables //

int newSpeed;

// Tasks //

TaskHandle_t FlashLEDTask;

// Helpers //

// This may or may not work, i have honestly no idea (the logic works, no clue with a live ESP tho)
void delayButNotDelay(int delayTimeInMs){
  // Input "delay" time in ms
  uint64_t timer = esp_timer_get_time();
  uint64_t pretime = esp_timer_get_time();
  uint64_t t = 0;

  while (t != delayTimeInMs){
    if(timer - pretime >= 1000) { // 1ms
      t++;
      pretime = timer;
    }
    timer = esp_timer_get_time();
  }
}

// WiFi //

void wifiEventListener(WiFiEvent_t event){
  switch (event) {
      case ARDUINO_EVENT_WIFI_READY: 
          Serial.println("WiFi: Interface ready");
          break;
      case ARDUINO_EVENT_WIFI_STA_CONNECTED:
          Serial.println("WiFi: Connected to ENGG2K3K Network");
          vTaskDelete(FlashLEDTask);
          break;
      case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
          Serial.println("WiFi: Disconnected from ENGG2K3K Network, Attempting to reconnect\n");
          setMotorDirection(1,1); 
          runMotor(0);
          // stop without our funny lil LEDs

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

  xTaskCreatePinnedToCore(
                  wifiFlashLED,   /* Task function. */
                  "WifiFlashLED",     /* name of task. */
                  2048,       /* Stack size of task */
                  NULL,        /* parameter of the task */
                  1,           /* priority of the task */
                  &FlashLEDTask,      /* Task handle to keep track of created task */
                  0);          /* pin task to core 0 */ 
  
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

  xTaskCreatePinnedToCore(
                    CCPFlashLED,   /* Task function. */
                    "CCPFlashLED",     /* name of task. */
                    2048,       /* Stack size of task */
                    NULL,        /* parameter of the task */
                    1,           /* priority of the task */
                    &FlashLEDTask,      /* Task handle to keep track of created task */
                    0);          /* pin task to core 0 */ 

  while(!client.connected() && WiFi.isConnected()){
    try{
      client.connect(ccpIP, ccpPort, 250);
    } catch (...){}
  }

  vTaskDelete(FlashLEDTask);
  
  // Logic purely here for the case where WiFi drops before we can contact the CCP
  if(WiFi.isConnected()){
    Serial.println("\nCCP: Connected");
    setLEDStatus(99);
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

void checkNetworkStatus(){
  if(!WiFi.isConnected()){
    setupWifi();
  }

  if(!client.connected()){
    setupCCP();
  }
}

// Hardware Functions //

void setupDoorServos(){
  pinMode(L_DOOR_SENSE_PIN, INPUT);
  pinMode(R_DOOR_SENSE_PIN, INPUT);
  leftdoor.attach(L_DOOR_PIN);
  rightdoor.attach(R_DOOR_PIN);
}

void setupLEDS(){
  NeoPixel.begin();
  NeoPixel.clear(); // once setup, wipe any colour that could be residually there from previous calls
  NeoPixel.show();
  NeoPixel.setBrightness(50); // so they don't blind us
}

void LEDFlash(int state){
  // Entire function is dedicated to creating a bluetooth pairing like flash
  static int flashon = 0;

  if (flashon == 0){
    flashon = 1;
    setLEDStatus(state);

  } else {
    flashon = 0;
    NeoPixel.clear();
  }

  NeoPixel.show();
}

void setLEDStatus(int state){
  static int red, green, blue;

  switch (state){
    case 0: // STOP - Red
      red = 255;
      green = 0;
      blue = 0;
      break;
    case 1: // FORWARD-SLOW - Lighter Green/Aquamarine-y
      red = 0;
      green = 255;
      blue = 40;
      break;
    case 2: // FORWARD-FAST - Green
      red =  50;
      green = 200;
      blue = 0;
      break;
    case 3: // REVERSE-SLOW - Light Blue (lighter = slow)
      red = 0;
      green = 70;
      blue = 200;
      break;
    case 4: // REVERSE-FAST - Dark Blue
      red = 0;
      green = 20;
      blue = 255;
      break;
    case 5: // DOOR-OPEN - Green
      red = 0;
      green = 255;
      blue = 0;
      break;
    case 6: // DOOR-CLOSE - Amber
      red = 255;
      green = 40;
      blue = 0;
      break;
    case 98: // DISCONNECTED, Not connected to Wifi
      red = 255;
      green = 40;
      blue = 0;
      break;
    case 99: // CONNECTED, no commands sent - BLUE
      red = 0;
      green = 0;
      blue = 255;
      break;
    default:
      Serial.println("Unknown status"); // White
      red = 255;
      green = 255;
      blue = 255;
      break;
  }

  for (int pixel = 0; pixel < NUM_PIXELS; pixel++){
    NeoPixel.setPixelColor(pixel, NeoPixel.Color(red, green, blue));
  }

  NeoPixel.show();
}

void setMotorDirection(int disable, int direction){
  if(disable == 1){
    digitalWrite(DIS_PIN, HIGH);
  } else {
    digitalWrite(DIS_PIN, LOW);
  }

  if(direction == 1){
    digitalWrite(DIR_PIN, LOW); // SHOULD BE HIGH
  } else {
    digitalWrite(DIR_PIN, HIGH); // SHOULD BE LOW
  }

  // THE ABOVE IS FLIPPED DUE TO A POLARITY MISMATCH ON THE CURRENT MODEL
}

void runMotor(int speed){
  analogWrite(PWM_PIN, speed);
}

void doorControlFlash(){
  // Sets a delay of 5000ms but allows for flashing lights to occur during this period purely for style
  for(int i = 0; i < 10; i++){
    LEDFlash(6);
    delay(500);
  }
}

void doorControl(int direction)
{
  if (direction == 1)
  { // door open; moves in clockwise direction
    leftdoor.write(45);
    rightdoor.write(45);
    //delay(5000); // rotates for 5 seconds
    doorControlFlash();
    leftdoor.write(90);
    rightdoor.write(90); // stops
  }
  else if (direction == -1)
  { // door close; moves in anticlockwise direction
    leftdoor.write(135);
    rightdoor.write(135);
    //delay(5000); // rotates for 5 seconds
    doorControlFlash();
    leftdoor.write(90); // stops
    rightdoor.write(90);
  }
}

// LED Flashes //

void wifiFlashLED(void * parameter){
  for(;;){
    LEDFlash(98);
    delay(500);
  }
}

void CCPFlashLED(void * parameter){
  for(;;){
    LEDFlash(99);
    delay(500);
  }
}

// ESP Actions //

void stop(){
  setLEDStatus(0);

  setMotorDirection(1,1); 
  runMotor(0);
  Serial.println("Stop Command");
}

void forwardSlow(){
  setLEDStatus(1);

  setMotorDirection(0,1);
  runMotor(slow_speed);
  Serial.println("Forward Slow Command");
}

void forwardFast(){
  setLEDStatus(2);

  setMotorDirection(0,1);
  runMotor(fast_speed);
  Serial.println("Forward Fast Command");
}

void reverseSlow(){
  setLEDStatus(3);

  setMotorDirection(0,0);
  runMotor(slow_speed);
  Serial.println("Reverse Slow Command");
}

void reverseFast(){
  setLEDStatus(4);

  setMotorDirection(0,0);
  runMotor(fast_speed);
  Serial.println("Reverse Fast Command");
}

void doorsOpen(){
  doorControl(1);
  setLEDStatus(5);
  Serial.println("Doors Open Command");
}

void doorsClose(){
  doorControl(-1);
  setLEDStatus(6);
  Serial.println("Doors Close Command");
}

void setFastSpeed(int newSpeed){
  //fast_speed = newSpeed;
  Serial.printf("Updated Fast Speed to: %d\n", newSpeed);
}

void setSlowSpeed(int newSpeed){
  //slow_speed = newSpeed;
  Serial.printf("Updated Slow Speed to: %d\n", newSpeed);
}

// CCP Listening //

void decipherCCPCommand(){
  if(client.connected() and client.available()){
    uint8_t data = client.read();  // Read a byte

    switch(data){
      case 0:
        stop();
        break;
      case 1:
        forwardSlow();
        break;
      case 2:
        forwardFast();
        break;
      case 3:
        reverseSlow();
        break;
      case 4:
        reverseFast();
        break;
      case 5:
        doorsOpen();
        break;
      case 6:
        doorsClose();
        break;
      case 7:
        while(!client.available()){}
        newSpeed = client.read();
        setSlowSpeed(newSpeed);
        break;
      case 8:
        while(!client.available()){}
        newSpeed = client.read();
        setFastSpeed(newSpeed);
        break;
      default:
        Serial.printf("Unknown ByteCode: 0x%02X\n", data);
        break;
    }

    if (data >= 0 && data <= 8){
      sendAckToCCP(data);
    }
  }

  if(!client.connected()){
    setupCCP();
  }
}

// Arduino/ESP Required Functions //

void setup() {
  Serial.begin(115200);
  setupLEDS();
  setupDoorServos();
  setupWifi();

  while(!WiFi.isConnected()){} // Blocking wait for WiFi before attempting CCP connection
  setupCCP();
}

void loop() {
  if (wifiReconnecting == 0 and ccpReconnecting == 0){
    // Check Health Status
    checkNetworkStatus();

    // Execute Commands Received
    decipherCCPCommand();
  }
}