#include <WiFi.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid     = "AndroidAFB94"; // Replace with LAN name and pass
const char* password = "Test1234";

// Server address and port
const char* serverIP = "192.168.125.177";  // Replace with the IP address of your local python server
const uint16_t serverPort = 3028;

void setup() {
  // Initialize Serial
  Serial.begin(115200);
  
  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
}

void loop() {
  // Connect to the TCP server
  static WiFiClient client;
  if (client.connect(serverIP, serverPort)) {
    Serial.println("Connected to server");

    // Buffer for receiving JSON data
    char buffer[512];
    
    // Read data from the server
    while (client.connected()) {
      if (client.available()) {
        // Read the incoming JSON data
        int length = client.readBytesUntil('\n', buffer, sizeof(buffer));
        buffer[length] = '\0'; // Null-terminate the string

        // Parse the JSON data
        StaticJsonDocument<512> doc;
        DeserializationError error = deserializeJson(doc, buffer);

        if (error) {
          Serial.print("Failed to parse JSON: ");
          Serial.println(error.c_str());
        } else {
          // Print the parsed JSON data
          Serial.println("Received JSON:");
          serializeJsonPretty(doc, Serial);
          Serial.println();

          if(doc["CMD"] == "SETUP"){
            // Create JSON data to send - Refer to ArduinoJson Assistant: https://arduinojson.org/v6/assistant/
            StaticJsonDocument<200> replydoc;
            replydoc["CMD"] = "SETUP_OK";

            // Serialize JSON data to a string
            String json_data;
            serializeJson(replydoc, json_data);

            // Send the JSON data to the server
            client.println(json_data);
            Serial.println("Sent JSON to server:");
            Serial.println(json_data);
          } else if (doc["CMD"] == "STATUS"){
            // Create JSON data to send - Refer to ArduinoJson Assistant: https://arduinojson.org/v6/assistant/
            StaticJsonDocument<200> replydoc;
            replydoc["STATUS"] = "NORMINAL";

            // Serialize JSON data to a string
            String json_data;
            serializeJson(replydoc, json_data);

            // Send the JSON data to the server
            client.println(json_data);
            Serial.println("Sent JSON to server:");
            Serial.println(json_data);
          }
        }
      }
    }
    client.stop();
    Serial.println("Disconnected from server");
  } else {
    Serial.println("Connection to server failed");
  }
}
