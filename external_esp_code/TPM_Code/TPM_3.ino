#include <Wire.h>
#include <Arduino.h>

#define IR_DOOR_ALIGN_PIN 18

void checkDoorAlignment(){
    int currIRVal = digitalRead(IR_DOOR_ALIGN_PIN);
    Serial.println(currIRVal);

    if (currIRVal == LOW){
      delay(150);
      Serial.println("We are now aligned to a station");
    }
}

void setup() {
  Serial.begin(115200);

  pinMode(IR_DOOR_ALIGN_PIN, INPUT_PULLUP);
}

void loop(){
    checkDoorAlignment();
}