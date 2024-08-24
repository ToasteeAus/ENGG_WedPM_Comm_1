#include <WiFi.h>

// WiFi credentials
const char* ssid     = "AndroidAFB94";
const char* password = "Test1234";

// Server address and port
const char* serverIP = "0.0.0.0";  // Replace with the IP address of your Python server
const uint16_t serverPort = 12345;

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

  // Connect to the TCP server
  WiFiClient client;
  if (client.connect(serverIP, serverPort)) {
    Serial.println("Connected to server");

    // Send data to the server
    String message = "Hello from ESP32";
    client.print(message);
    Serial.println("Message sent: " + message);

    // Wait for the server's response
    while (client.available() == 0);
    String response = client.readString();
    Serial.println("Received from server: " + response);

    // Close the connection
    client.stop();
    Serial.println("Disconnected from server");
  } else {
    Serial.println("Connection to server failed");
  }
}

void loop() {
  // Do nothing in loop
}
