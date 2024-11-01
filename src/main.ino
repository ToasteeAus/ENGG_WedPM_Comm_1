#include <WiFi.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <RCWL_1X05.h>
#include <Adafruit_NeoPixel.h>
#include "XT_DAC_Audio.h"
#include "SoundData.h"


// TODO: FIX STATUS LEDS WHEN DOORS CLOSING AND OPENING + RE-ADD FLASH FOR FLARE
/*
  CRITICAL NOTE: DO NOT SEND PRINTLN COMMANDS TO PYTHON SERVER, IT HAS A FIT <3
  Remove all Serial statements when we produce the production variant of this code with all systems operational
*/

// Motor Pin Definitions
#define DIS_PIN 15
#define DIR_PIN 13
#define PWM_PIN 12

// Door Pin Definitions
#define R_DOOR_PIN 23
#define L_DOOR_PIN 27
#define R_DOOR_SENSE_PIN 35
#define L_DOOR_SENSE_PIN 34
#define IR_DOOR_ALIGN_PIN 18

// Power Management System Pin Definitions
#define B_SENSE 33 // BSENSE - 0 -> 3.3v proportional to 0 - 12.6v of the battery
#define FIVE_RAW 32 // 5VRaw - 0 -> 3.3v to 0 - 5v -> Will drop when battery drops (Battery Trigger)
// VP, VC -> Not necessary but nice to have
// BMS, When BSEnse drops below 9.6v (proportional) -> stop, disconnect, to MCP, then set to DISCONNECT state

// Rear facing ultrasonic
#define TRIG_PIN 2 // Rear facing Ultrasonic
#define ECHO_PIN 5 // Rear facing Ultrasonic

// Status LEDs
#define PIN_NEO_PIXEL 4
#define NUM_PIXELS 4    // The number of LEDs in sequence

// Audio System
#define AUDIO_PIN 25
XT_Wav_Class doorsCloser(doorsClosing);
XT_DAC_Audio_Class DacAudio(AUDIO_PIN, 0);

// WiFi credentials
const char* ssid     = "ENGG2K3K"; // Replace with LAN name and pass
const char* password = "";

// WiFi/Client status ints
int wifiReconnecting = 0;
int ccpReconnecting = 0;
bool disconnected = false;

// // Static IP configuration
IPAddress staticIP(10, 20, 30, 128); // ESP32 static IP
IPAddress gateway(10, 20, 30, 250);    // IP Address of your network gateway (router)
IPAddress subnet(255, 255, 255, 0);   // Subnet mask
IPAddress primaryDNS(10, 20, 30, 1); // Primary DNS (optional)
IPAddress secondaryDNS(0, 0, 0, 0);   // Secondary DNS (optional)

// Server address and port
const char* ccpIP = "10.20.30.1";  // Replace with the IP address of your local python server
const uint16_t ccpPort = 3028;

// Motor Speeds
const int fast_speed = 255; // Ensure speeds are set such that if divided by our speed_interval, they return ints not doubles
const int slow_speed = 100;
int target_speed = 0;
int curr_speed = 0;
int speed_interval = 5;

// Status Checks
int checkForStation = 0;
int atStation = 0;

// Collision Detection
int detectCount = 0;
int detectorSelected = 0; // 1 for front, -1 for rear

// Class Object Constructors
Adafruit_NeoPixel NeoPixel(NUM_PIXELS, PIN_NEO_PIXEL, NEO_GRB + NEO_KHZ800);
RCWL_1X05 frontUltraSonic;
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
TaskHandle_t DoorTaskHandle;

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
    stop();
    setupWifi();
  }

  if(!client.connected()){
    stop();
    setupCCP();
  }
}

// Hardware Functions //

void setupDoorServos(){
  pinMode(L_DOOR_SENSE_PIN, INPUT); // HARDWARE PULLUP
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
    case 96: // DOOR-ALIGN, Detected
      red = 255;
      green = 0;
      blue = 255;
      break;
    case 97: // COLLISION, Detected
      red = 0;
      green = 255;
      blue = 255;
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

void setupMotorPins(){
  pinMode(DIS_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(PWM_PIN, OUTPUT);
}

void setMotorDirection(int disable, int direction){
  if(disable == 1){
    digitalWrite(DIS_PIN, HIGH);
  } else if (disable == 0) {
    digitalWrite(DIS_PIN, LOW);
  }

  if(direction == 1){
    digitalWrite(DIR_PIN, HIGH); // SHOULD BE LOW ON PRIOR to V2 BR
  } else if (direction == 0){
    digitalWrite(DIR_PIN, LOW); // SHOULD BE HIGH ON PRIOR TO V2 BR
  }

  // THE ABOVE IS FLIPPED DUE TO A POLARITY MISMATCH ON THE CURRENT MODEL
}

void runMotor(int speed){
  analogWrite(PWM_PIN, speed);
}

void doorControlDelayFlash(){
  LEDFlash(6);
  delay(500);
  LEDFlash(6);
  delay(430);
}

void doorControl(int dir)
{
  // xTask is a backup possible solution for the door Flashing code in case our delay one is causing too many hiccups down the line with the rest of our system
  // But this shouldn't impact too much as this only occurs when STOPPED and AT STATION so we shouldnt see it impact nominal ops
  
  if (dir == 1)
  { // door open; moves in clockwise direction
    leftdoor.write(45);
    rightdoor.write(135);
    doorControlDelayFlash();
    leftdoor.write(90);
    rightdoor.write(90);
    setLEDStatus(5);
  }
  else if (dir == -1)
  { // door close; moves in anticlockwise direction
    xTaskCreate(
      doorFlashLED,   
      "DoorFlashLED",    
      2048,               
      NULL,           
      1,                  
      &FlashLEDTask    
    );

    leftdoor.write(135);
    rightdoor.write(45);
    int leftShut = 0;
    int rightShut = 0;

    while(leftShut == 0 or rightShut == 0){
      if (leftShut == 0){
        if(digitalRead(L_DOOR_SENSE_PIN) == LOW){ // Hardware Pullup
          Serial.println("Left Door Shut");
          delay(1); // debounce
          leftShut = 1;
          leftdoor.write(90); // Some values may need to be 95 instead of 90
        }
      }

      if(rightShut == 0){
        if(digitalRead(R_DOOR_SENSE_PIN) == LOW){
          Serial.println("Right Door Shut");
          delay(1); // debounce
          rightShut = 1;
          rightdoor.write(90);
        }
      }
    }
    vTaskDelete(FlashLEDTask);
    setLEDStatus(6);
  }

  // Just in case it wasn't deleted:
}

void setupUltrasonic(){
  Wire.begin();
  frontUltraSonic.begin();
  frontUltraSonic.setTimeout(40); // 30ms time out for testing, may need to be increased
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT_PULLUP);
}

void rearCollisionDetection(){
  if (atStation == 0){ // If we re-adjust the ultrasonic cones then we should be able to safely remove this check
    delay(5);
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long rawPulse = pulseIn(ECHO_PIN, HIGH, 30000);
    // 29 microseconds per centimeter at the speed of sound, divided by half of the distance travelled
    long dist = (rawPulse / 2) * 0.0343;
    Serial.printf("Distance measured in cm: %d", dist); // if pulse is less than or equal to 320
    if (dist <= 5){ // distances make 0 sense anymore
      detectCount++;
    }
    
    if (checkForStation == 1){
      if (detectCount == 3){
        sendAlertToCCP(0xAB);
        setLEDStatus(97);
        setMotorDirection(1,1); 
        runMotor(0);
        checkForStation = 0;
        detectCount = 0;
        detectorSelected = 0;
      }
    } else {
      if (detectCount == 9){
        sendAlertToCCP(0xAB);
        setLEDStatus(97);
        setMotorDirection(1,1); 
        runMotor(0);
        checkForStation = 0;
        detectCount = 0;
        detectorSelected = 0;
      }
    }
  }
}

void frontCollisionDetection(){
  if (atStation == 0){ // If we re-adjust the ultrasonic cones then we should be able to safely remove this check
    frontUltraSonic.setMode(RCWL_1X05::triggered);
    frontUltraSonic.trigger();

    delay(100); // may want to re-assess the delay time
    int checkTime = millis();
    int rawUltraSonicData = frontUltraSonic.read();
    int finalTime = millis();

    if (finalTime - checkTime <= 40){ // Logic explanation, if the detection range is outside of 40ms from when we triggered the ultrasonic, we treat it as tho it timed out
      if (rawUltraSonicData <= 250){ // Currently using a 250mm distance as its the lowest amount it should *safely* discern but this can be revised
        // TODO: Implement check for time-gap between detections to ensure recency of detections
        // If the gap between the most recent and the last has surpased 500ms, we clear the last group of detections and consider it 1 again
        detectCount++;
      }
    }
    
    if (checkForStation == 1){
      if (detectCount == 9){
        sendAlertToCCP(0xAB);
        setLEDStatus(97);
        setMotorDirection(1,1); 
        runMotor(0);
        target_speed = 0;
        checkForStation = 0;
        detectCount = 0;
        detectorSelected = 0;
      }
    } else {
      if (detectCount == 35){
        sendAlertToCCP(0xAB);
        setLEDStatus(97);
        setMotorDirection(1,1); 
        runMotor(0);
        target_speed = 0;
        checkForStation = 0;
        detectCount = 0;
        detectorSelected = 0;
      }
    }
  }
}

void checkDoorAlignment(){
  if (checkForStation == 1){
    int currIRVal = digitalRead(IR_DOOR_ALIGN_PIN);
    Serial.println(currIRVal);

    if (currIRVal == LOW){
      delay(150);
      //stop();
      runMotor(0); // Let's immediately stop on alignment
      Serial.println("We are now aligned to a station");
      sendAlertToCCP(0xAA); // AA for Station alignment
      setLEDStatus(96);
      checkForStation = 0;
      // Insert Code to alert back we are stopped at a station
      atStation = 1;
    } else {
      Serial.println("We aren't at a station");
    }
  }

}

void setupBatteryPins(){
  pinMode(B_SENSE, INPUT);
  pinMode(FIVE_RAW, INPUT);
}

// LED Flashes //

void wifiFlashLED(void * parameter){
  for(;;){
    LEDFlash(98);
    vTaskDelay(500 / portTICK_PERIOD_MS);
  }
}

void CCPFlashLED(void * parameter){
  for(;;){
    LEDFlash(99);
    vTaskDelay(500 / portTICK_PERIOD_MS);
  }
}

void doorFlashLED(void * parameter){
  for(;;){
    LEDFlash(6);
    vTaskDelay(500 / portTICK_PERIOD_MS);
  }
}

void DisconnectFlashLED(){
  for(;;){
    LEDFlash(0);
    delay(500);
  }
}

// ESP Actions //

void stop(){
  setLEDStatus(0);
  detectCount = 0;

  setMotorDirection(1,1); 
  set_target_speed(0);
  checkForStation = 0;
  Serial.println("Stop Command");
}

void forwardSlow(){
  detectorSelected = 1;
  detectCount = 0;
  setLEDStatus(1);
  setMotorDirection(0, 1);

  set_target_speed(slow_speed);
  checkForStation = 1;
  Serial.println("Forward Slow Command");
}

void forwardFast(){
  detectorSelected = 1;
  detectCount = 0;
  setLEDStatus(2);

  setMotorDirection(0,1);
  set_target_speed(fast_speed);
  checkForStation = 0;
  atStation = 0;
  Serial.println("Forward Fast Command");
}

void reverseSlow(){
  detectorSelected = -1;
  detectCount = 0;
  setLEDStatus(3);

  setMotorDirection(0,0);
  if (curr_speed == 0){
    curr_speed = 25;
  }
  
  set_target_speed(slow_speed);
  checkForStation = 1;
  Serial.println("Reverse Slow Command");
}

void reverseFast(){
  detectorSelected = -1;
  detectCount = 0;
  setLEDStatus(4);

  setMotorDirection(0,0);
  if (curr_speed == 0){
    curr_speed = 25;
  }
  set_target_speed(fast_speed);
  checkForStation = 0;
  Serial.println("Reverse Fast Command");
}

void doorsOpen(){
  int direction = 1;
  checkForStation = 0;

  doorControl(direction);
  Serial.println("Doors Open Command");
}

void doorsClose(){
  int direction = -1;
  checkForStation = 0;

  doorControl(direction);
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

void disconnect(){
  setMotorDirection(1,1); 
  runMotor(0); // Exception to the rule, if we are in disconnect, all bets are off, do not roll forward

  disconnected = true;
  sendAlertToCCP(0xFF);

  WiFi.disconnect(true, true); 
  Serial.print("Awaiting Removal from Track");
  DisconnectFlashLED();
}

void batteryStatus(){
  // BSENSE - 0 -> 3.3v proportional to 0 - 12.6v of the battery
  // 5VRaw - 0 -> 3.3v to 0 - 5v -> Will drop when battery drops (Battery Trigger)
  // VP, VC -> Not necessary but nice to have
  // BMS, When BSEnse drops below 9.0v (proportional) -> stop, disconnect, to MCP, then set to DISCONNECT state

  int currBatteryVoltage = analogRead(B_SENSE);
  double batteryProportionalVoltage = (12.5 / 4096) * currBatteryVoltage;

  int currFiveRailVoltage = analogRead(FIVE_RAW);
  double fiveRailProportionalVoltage = (5.0 / 4096) * currFiveRailVoltage;

  if(fiveRailProportionalVoltage <= 3.9 || batteryProportionalVoltage <= 5.0){ // fiveRailProportionalVoltage <= 4.9 ||
    sendAlertToCCP(0xFE);
    setMotorDirection(1,1); 
    runMotor(0);
    DisconnectFlashLED();
  }

  Serial.print("\nBMS - BATTERY VOLTAGE: ");
  Serial.print(batteryProportionalVoltage);

  Serial.print("\nBMS - FIVE VOLT RAIL: ");
  Serial.print(fiveRailProportionalVoltage);

}

void set_target_speed(int newSpeed){
  target_speed = newSpeed;
}

void drive_motor(){
  if (curr_speed != target_speed){
    int temp_speed;
    
    if (target_speed < curr_speed){
      temp_speed = curr_speed - speed_interval;
    } else if (target_speed > curr_speed){
      temp_speed = curr_speed + speed_interval;
    }

    temp_speed = constrain(temp_speed, 0, fast_speed);
    runMotor(temp_speed);
    curr_speed = temp_speed;
  }
}

void playAudio(){
  DacAudio.FillBuffer();                // Fill the sound buffer with data
  Serial.println(DacAudio.BufferUsage());
  Serial.println(doorsCloser.PlayingTime);
  if(doorsCloser.Playing==false)       // if not playing,
    DacAudio.Play(&doorsCloser);
    delay(doorsCloser.PlayingTime);
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
      case 0xEE:
        playAudio();
        break;
      case 0xFF:
        disconnect();
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

// Arduino/ESP Required Functions //

void setup() {
  Serial.begin(115200);
  setupBatteryPins();
  setupMotorPins();
  setMotorDirection(1, 1); // Test reseting the motor direction
  
  setupLEDS();
  pinMode(IR_DOOR_ALIGN_PIN, INPUT_PULLUP);
  setupDoorServos();
  setupUltrasonic();
  
  setupWifi();

  while(!WiFi.isConnected()){} // Blocking wait for WiFi before attempting CCP connection
  setupCCP();
}

void loop() {
  batteryStatus();
  if (disconnected == false){
    if (wifiReconnecting == 0 and ccpReconnecting == 0){
      // Before we do anytihng, check we aren't going to crash into something
      // May add check that we aren't in station searching mode
      // if (detectorSelected == 1){
      //   frontCollisionDetection();
      // } else if (detectorSelected == -1){
      //   //rearCollisionDetection();
      // }
      
      // Check Health Status
      checkNetworkStatus();

      // Drive our Motors to check or meet the newest speed - important to do this after collision detection in case of positive hit
      drive_motor();

      // Execute Commands Received
      decipherCCPCommand();

      // Check we aren't now somehow at a station
      // This could be changed to an interrupt event
      checkDoorAlignment();
    } else {
      stop();
    }
  } else {
    stop();
  }
}