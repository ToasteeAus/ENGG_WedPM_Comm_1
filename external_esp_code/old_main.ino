#include <WiFi.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Adafruit_NeoPixel.h>

/*
  CRITICAL NOTE: DO NOT SEND PRINTLN COMMANDS TO PYTHON SERVER, IT HAS A FIT <3
*/

// Pin definitions
#define DIS_PIN 15
#define DIR_PIN 13
#define PWM_PIN 12
#define DOOR_PIN 25
#define PIN_NEO_PIXEL 4

// Status LEDs
#define NUM_PIXELS 4    // The number of LEDs in sequence

// WiFi credentials
const char* ssid     = "ENGG2K3K"; // Replace with LAN name and pass
const char* password = "";

// Static IP configuration
IPAddress staticIP(10, 20, 30, 128); // ESP32 static IP
IPAddress gateway(10, 20, 30, 250);    // IP Address of your network gateway (router)
IPAddress subnet(255, 255, 255, 0);   // Subnet mask
IPAddress primaryDNS(10, 20, 30, 1); // Primary DNS (optional)
IPAddress secondaryDNS(0, 0, 0, 0);   // Secondary DNS (optional)

// Server address and port
const char* serverIP = "10.20.30.1";  // Replace with the IP address of your local python server
const uint16_t serverPort = 3028;

// Station and Motor Speeds
int fast_speed = 255;
int slow_speed = 150;
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
      LEDFlash(255, 40, 0);
    }

    if(!WiFi.config(staticIP, gateway, subnet, primaryDNS, secondaryDNS)) {
      Serial.println("Failed to configure Static IP");
    } else {
      Serial.println("Static IP configured!");
      Serial.println(WiFi.localIP());
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
  } else if (staticJson["CMD"] == "LIGHT"){ // Only here for testing lighting options in static offsite tests
    
    int red = staticJson["RED"];
    int green = staticJson["GREEN"];
    int blue = staticJson["BLUE"];

    for (int pixel = 0; pixel < NUM_PIXELS; pixel++){
      NeoPixel.setPixelColor(pixel, NeoPixel.Color(red, green, blue));
    }
    NeoPixel.show();

    replydoc["ACK"] = "LIGHT_OK";
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
  } else if (staticJson["CMD"] == "SLOWSPEEDSET"){
    slow_speed = int(staticJson["SPEED"]);
    replydoc["ACK"] = "SLOWSPEEDSET_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "FASTSPEEDSET"){
    fast_speed = int(staticJson["SPEED"]);
    replydoc["ACK"] = "FASTSPEEDSET_OK";
    sendToCCP(replydoc, client);

  } else if (staticJson["CMD"] == "FORWARD_FAST"){
    setLEDStatus(1);
    setMotorDirection(0,1);
    runMotor(fast_speed);
    replydoc["ACK"] = "FORWARD_FAST_OK";
    sendToCCP(replydoc, client);
    
  } else if (staticJson["CMD"] == "FORWARD_SLOW"){
    setLEDStatus(2);
    setMotorDirection(0,1);
    runMotor(slow_speed);
    replydoc["ACK"] = "FORWARD_SLOW_OK";
    sendToCCP(replydoc, client);

  } else if (staticJson["CMD"] == "REVERSE_SLOW"){
    setLEDStatus(3);
    setMotorDirection(0,0);
    runMotor(slow_speed);
    replydoc["ACK"] = "REVERSE_SLOW_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "REVERSE_FAST"){
    setLEDStatus(4);
    setMotorDirection(0,0);
    runMotor(fast_speed);
    replydoc["ACK"] = "REVERSE_FAST_OK";
    sendToCCP(replydoc, client);
  } else if (staticJson["CMD"] == "DOOR_OPEN"){
    replydoc["ACK"] = "DOOR_OPEN_OK";
    sendToCCP(replydoc, client);

    doorControl(1);
    setLEDStatus(5);
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
    case 1: // FORWARD-FAST - Green
      red =  50;
      green = 200;
      blue = 0;
      break;
    case 2: // FORWARD-SLOW - Lighter Green/Aquamarine-y
      red = 0;
      green = 255;
      blue = 40;
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
    LEDFlash(255, 60, 0);
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
  // Emptying, TODO: 
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

  // Add in self testing code ->
  // Check for existence of LEDs, Sensors, Motors etc.
  // Debug statement sent in SETUP_OK or using LED status lights

  setupNetworks();
}

void loop() {
  StaticJsonDocument<512> staticJsonResponse;

  if (client.connected() and WiFi.isConnected()){
    // Listen to TCP Server for commands
    if (client.available()) {
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