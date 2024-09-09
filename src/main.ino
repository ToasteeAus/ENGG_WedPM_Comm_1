#include <WiFi.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>

/*
  CRITICAL NOTE: DO NOT SEND PRINTLN COMMANDS TO PYTHON SERVER, IT HAS A FIT <3
*/

// Pin definitions
#define DIS_PIN 15
#define DIR_PIN 16
#define PWM_PIN 17
#define DOOR_PIN 26 
#define PHOTORESISTOR_PIN 26
#define PIN_NEO_PIXEL 4 // Schematic shows pin as GPIO4

// Status LEDs
#define NUM_PIXELS 4    // The number of LEDs in sequence

// WiFi credentials
const char* ssid     = "AndroidAFB94"; // Replace with LAN name and pass
const char* password = "Test1234";

// Server address and port
const char* serverIP = "192.168.212.177";  // Replace with the IP address of your local python server
const uint16_t serverPort = 3028;

// Station and Motor Speeds
#define FAST_SPEED 255
#define SLOW_SPEED 150
int atStation = 0;

// Class Object Constructors
Adafruit_NeoPixel NeoPixel(NUM_PIXELS, PIN_NEO_PIXEL, NEO_GRB + NEO_KHZ800);
WiFiClient client;
Servo door;

// Core Comms Functions //

void setupWifi(){
  // Connect to Wi-Fi
  Serial.print("WiFi: Connecting");
  // WiFi.config(10.20.30.128) // forces the ESP32 to use our given IP address
  if (!WiFi.isConnected()){ // solely to protect against erroneous calls
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
      LEDFlash(255, 165, 0);
    }

  Serial.println("\nWiFi: Connected");
  }
}

void setupCCP(){
  Serial.print("CCP: Connecting");

  while(!client.connected()){
    if (!WiFi.isConnected()){ // Prevent issues with socket failing with WiFi dying during connection
      setupWifi();
    } else {
      try{
        client.connect(serverIP, serverPort, 250);
      } catch (...){

      }
    }
    delay(250); // Simply to ease the flashing and reduce Serial Monitor logs
    Serial.print(".");
    LEDFlash(0, 0, 255);
  }
  Serial.println("\nCCP: Connected");
  setLEDStatus(99);
}

void setupNetworks(){
  setupWifi();
  setupCCP();
}

// Main Execution Logic //

void readFromCCP(JsonDocument &staticJson){
  // We assume we are connected by this point

  // Buffer for receiving JSON data
  static char buffer[512];
  // Read the incoming JSON data
  int length = client.readBytesUntil('\n', buffer, sizeof(buffer));
  buffer[length] = '\0'; // Null-terminate the string

  DeserializationError error = deserializeJson(staticJson, buffer);

  if (error) {
    Serial.print("Failed to parse JSON: ");
    Serial.println(error.c_str());
  } else {
    // Print the parsed JSON data
    Serial.println("Received JSON:");
    serializeJsonPretty(staticJson, Serial);
    Serial.println();
  }
}

void sendToCCP(JsonDocument &staticJson, WiFiClient &client){
  // Serialize JSON data to a string
  String json_data;
  serializeJson(staticJson, json_data);

  // Send the JSON data to the server
  client.print(json_data);

  Serial.println("Sent JSON to server:");
  Serial.println(json_data);
}

void execFromCCP(JsonDocument &staticJson){
  StaticJsonDocument<200> replydoc;

  // due to the unfortunate nature of C++ not recognising strings for switch statements, here is this mess
  // For Collisions that the ESP detect, send the following message structure:
  // {"ALERT":"COLLISION"}
  if(staticJson["CMD"] == "SETUP"){
    setLEDStatus(0);
    runMotor(0);
    setMotorDirection(1,1); 
    replydoc["ACK"] = "SETUP_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "STATUS"){
    replydoc["ACK"] = "NORMINAL";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "STOP"){
    setLEDStatus(0);
    runMotor(0);
    setMotorDirection(1,1); 
    replydoc["ACK"] = "STOP_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "FORWARD_FAST"){
    setLEDStatus(1);
    setMotorDirection(0,1);
    runMotor(FAST_SPEED);
    replydoc["ACK"] = "FORWARD_FAST_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "FORWARD_SLOW"){
    setLEDStatus(2);
    setMotorDirection(0,1);
    runMotor(SLOW_SPEED);
    replydoc["ACK"] = "FORWARD_SLOW_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "REVERSE_SLOW"){
    setLEDStatus(3);
    setMotorDirection(0,0);
    runMotor(SLOW_SPEED);
    replydoc["ACK"] = "REVERSE_SLOW_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "REVERSE_FAST"){
    setLEDStatus(4);
    setMotorDirection(0,0);
    runMotor(FAST_SPEED);
    replydoc["ACK"] = "REVERSE_FAST_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "DOOR_OPEN"){
    replydoc["ACK"] = "DOOR_OPEN_OK";
    sendToCCP(replydoc, client);

    doorControl(1);
    setLEDStatus(5);

    replydoc.clear(); // TODO: DELETE THESE LINES BEFORE BRINGING INTO PRODUCTION
    replydoc["ALERT"] = "STOPPED_AT_STATION";

    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "DOOR_CLOSE"){
    replydoc["ACK"] = "DOOR_CLOSE_OK"; // Unique Bug, if this reply is set to fire after the door control event + status LED, the CCP timesout too long after its complete
    sendToCCP(replydoc, client);

    doorControl(-1);
    setLEDStatus(0);
  }
  
  replydoc.clear();
}

// Hardware Functions //
void setupLEDS(){
  NeoPixel.begin();
  NeoPixel.clear(); // once setup, wipe any colour that could be residually there from previous calls
  NeoPixel.show();
  NeoPixel.setBrightness(50); // so they don't blind us
}

void LEDFlash(int red, int green, int blue){
  // Entire function is dedicated to creating a bluetooth pairing like flash
  static int flashon = 0;
  if (flashon == 0){
    flashon = 1;
    for (int pixel = 0; pixel < NUM_PIXELS; pixel++){
      NeoPixel.setPixelColor(pixel, NeoPixel.Color(red, green, blue));
    }
  } else {
    flashon = 0;
    NeoPixel.clear();
  }
  NeoPixel.show();
}

void setLEDStatus(int status){
  static int red, green, blue;
  switch (status){
    case 0: // STOP - Red
      red = 255;
      green = 0;
      blue = 0;
      break;
    case 1: // FORWARD-FAST - Light Green
      red =  88;
      green = 214;
      blue = 141;
      break;
    case 2: // FORWARD-SLOW - Dark Green
      red = 30;
      green = 132;
      blue = 73;
    case 3: // REVERSE-SLOW - Dark Blue
      red = 26;
      green = 82;
      blue = 118;
      break;
    case 4: // REVERSE-FAST - Light Blue
      red = 46;
      green = 134;
      blue = 193;
      break;
    case 5: // DOOR-OPEN - Green
      red = 0;
      green = 128;
      blue = 0;
      break;
    case 6: // DOOR-CLOSE - Amber
      red = 255;
      green = 191;
      blue = 0;
      break;
    case 99: // CONNECTED, no commands sent - BLUE
      red = 0;
      green = 0;
      blue = 255;
      break;
    default:
      Serial.println("Unknown status");
      red = 255;
      green = 255;
      blue = 255;
  }

  for (int pixel = 0; pixel < NUM_PIXELS; pixel++){
    NeoPixel.setPixelColor(pixel, NeoPixel.Color(red, green, blue));
  }
  NeoPixel.show();
}

void setMotorDirection(int disable, int direction){
  if(disable==1){
    digitalWrite(DIS_PIN, HIGH);
  } else {
    digitalWrite(DIS_PIN, LOW);
  }

  if(direction==1){
    digitalWrite(DIR_PIN, HIGH);
  } else {
    digitalWrite(DIR_PIN, LOW);
  }
}

void runMotor(int speed){
  analogWrite(PWM_PIN, speed);
}

void softAcceleration(int currSpeed, int newSpeed){
  //TODO add function to smooth out acceleration
}

void readPhotoresistor(WiFiClient &client){
  int value = analogRead(PHOTORESISTOR_PIN);

  if(value > 450){
    runMotor(0);
    setMotorDirection(1, 1);
    /*if(atStation == 0){
        if(client.connected() && client.available()){
          StaticJsonDocument<200> messageDoc;
          messageDoc["UPDATE"] = "EMERGENCY_STOP";
          sendToCCP(messageDoc, client);
          messageDoc.clear();
        }
    }
    */
    if(atStation == 1){
      doorControl(1);
    }
  }
}

void doorControlFlash(){
  // Sets a delay of 5000ms but allows for flashing lights to occur during this period purely for style
  for(int i = 0; i < 10; i++){
    LEDFlash(255, 191, 0);
    delay(500);
  }
}

void doorControl(int direction) {
 
  if (direction == 1) { // door open; moves in clockwise direction
    door.write(45);
    //delay(5000); // rotates for 5 seconds
    doorControlFlash();
    door.write(90); // stops
    } 
  else if (direction == -1) { // door close; moves in anticlockwise direction
    door.write(135);
    //delay(5000); // rotates for 5 seconds
    doorControlFlash();
    door.write(90); // stops
    }
}

void readUltrasonic(){
  //Wire.requestFrom(0x57, 32);
  //long dist = Wire.read();
}

// Arduino/ESP Required Functions //

void setup() {
  // Initialize Serial
  Serial.begin(115200);
  setupLEDS();

  door.attach(DOOR_PIN); // for controlling the door operations
  // set motor pins to outputs
  pinMode(DIS_PIN, OUTPUT); 
  pinMode(DIR_PIN, OUTPUT);
  pinMode(PWM_PIN, OUTPUT);
  //Wire.begin();

  setupNetworks();
}

void loop() {
  StaticJsonDocument<512> staticJsonResponse;

  if (client.connected() and WiFi.isConnected()){
    // Listen to TCP Server for commands
    if (client.available()) {
      //readPhotoresistor(client);
      // Read info from Python Server
      readFromCCP(staticJsonResponse);

      if (!staticJsonResponse.isNull()){
        execFromCCP(staticJsonResponse);
      }
    }
    // Technically a clear isn't necessary but this prevents any leftover json data from our next read cycle
    staticJsonResponse.clear();
  } else {
    // WiFi or CCP have died, check both
    Serial.println("URGENT: LOST COMMS, RE-ESTABLISHING");
    runMotor(0);
    setMotorDirection(1, 1);
    setupNetworks();
  }
}