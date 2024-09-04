#include <WiFi.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

/*
  CRITICAL NOTE: DO NOT SEND PRINTLN COMMANDS TO PYTHON SERVER, IT HAS A FIT <3
*/

// Pin definitions
#define PIN_NEO_PIXEL 4 // Schematic shows pin as GPIO4

// Status LEDs
#define NUM_PIXELS 4    // The number of LEDs in sequence
Adafruit_NeoPixel NeoPixel(NUM_PIXELS, PIN_NEO_PIXEL, NEO_GRB + NEO_KHZ800);

// WiFi credentials
const char* ssid     = "AndroidAFB94"; // Replace with LAN name and pass
const char* password = "Test1234";

// Server address and port
const char* serverIP = "192.168.212.233";  // Replace with the IP address of your local python server
const uint16_t serverPort = 3028;

void setupWifi(){
  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
}

void readFromCCP(JsonDocument &staticJson, WiFiClient &client){
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

void setLEDStatus(int status){
  static int red, green, blue;
  switch (status){
    case 0: // STOP - Red
      red = 255;
      green = 0;
      blue = 0;
      break;
    case 1: // FORWARD-FAST - White
      red = 255;
      green = 255;
      blue = 255;
      break;
    case 2: // FORWARD-SLOW - Light Blue
    case 3: // REVERSE-SLOW - Light Blue
      red = 149;
      green = 216;
      blue = 247;
      break;
    case 4: // REVERSE-FAST - Grey
      red = 170;
      green = 170;
      blue = 170;
      break;
    case 5: // DOOR-OPEN - Green
      red = 49;
      green = 164;
      blue = 88;
      break;
    case 6: // DOOR-CLOSE - Amber
      red = 234;
      green = 167;
      blue = 25;
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

void setup() {
  // Initialize Serial
  Serial.begin(115200);
  NeoPixel.begin();
  NeoPixel.clear(); // once setup, wipe any colour that could be residually there from previous calls
  NeoPixel.show();
  NeoPixel.setBrightness(50); // so they don't blind us
  setupWifi();
}

void loop() {
  // Connect to the TCP server
  static WiFiClient client;
  // reusable staticjsondoc
  StaticJsonDocument<512> staticJsonResponse;

  if (client.connect(serverIP, serverPort)) {
    Serial.println("Connected to server");

    // Read data from the server
    while (client.connected()) {
      if (client.available()) {
        // Read info from Python Server
        readFromCCP(staticJsonResponse, client);

        if (!staticJsonResponse.isNull()){
          StaticJsonDocument<200> replydoc;
          // due to the unfortunate nature of C++ not recognising strings for switch statements, here is this mess
          if(staticJsonResponse["CMD"] == "SETUP"){
            replydoc["ACK"] = "SETUP_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "STATUS"){
            replydoc["ACK"] = "NORMINAL";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "STOP"){
            setLEDStatus(0); 
            replydoc["ACK"] = "STOP_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "FORWARD_FAST"){
            setLEDStatus(1);
            replydoc["ACK"] = "FORWARD_FAST_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "FORWARD_SLOW"){
            setLEDStatus(2);
            replydoc["ACK"] = "FORWARD_SLOW_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "REVERSE_SLOW"){
            setLEDStatus(3);
            replydoc["ACK"] = "REVERSE_SLOW_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "REVERSE_FAST"){
            setLEDStatus(4);
            replydoc["ACK"] = "REVERSE_FAST_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "DOOR_OPEN"){
            setLEDStatus(5);
            replydoc["ACK"] = "DOOR_OPEN_OK";
            sendToCCP(replydoc, client);
          } else if (staticJsonResponse["CMD"] == "DOOR_CLOSE"){
            setLEDStatus(6);
            replydoc["ACK"] = "DOOR_CLOSE_OK";
            sendToCCP(replydoc, client);
          }
          
          replydoc.clear();

        }
      }
      // Technically a clear isn't necessary but this prevents any leftover json data from our next read cycle
      staticJsonResponse.clear();
    }
    client.stop();
    Serial.println("Disconnected from server");
  } else {
    Serial.println("Connection to server failed");
    NeoPixel.clear(); // wipe to confirm BR is unresponsive
    NeoPixel.show();
  }
}
