#include <Wifi.h>
#include <config.h>
#include <Arduino.h>

// Use the inbuilt Wifi library to attempt to join the network
// Connection uses Wifi Pass + Name in config.h
void connect_wifi(){
    while(WiFi.status() != WL_CONNECTED){
        WiFi.mode(WIFI_STA);
        WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
        delay(500);
    }
}

// Initialise Wifi by attempting to connect
// Once successful, task ends itself
static void init_wifi(void*){
    connect_wifi();
    vTaskDelete(NULL);
}

String heartbeat(){
    return "Heartbeat Status: " + (String)WiFi.status();
}