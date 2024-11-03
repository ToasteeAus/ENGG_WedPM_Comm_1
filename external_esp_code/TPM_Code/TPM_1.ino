#include <Adafruit_NeoPixel.h>
#include <Arduino.h>

// Status LEDs
#define PIN_NEO_PIXEL 4
#define NUM_PIXELS 4

// Class Object Constructors
Adafruit_NeoPixel NeoPixel(NUM_PIXELS, PIN_NEO_PIXEL, NEO_GRB + NEO_KHZ800);

void setupLEDS(){
  NeoPixel.begin();
  NeoPixel.clear(); // once setup, wipe any colour that could be residually there from previous calls
  NeoPixel.show();
  NeoPixel.setBrightness(50); // so they don't blind us
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

void setup(){
    setupLEDS();
}

void loop(){
    setLEDStatus(0);
}