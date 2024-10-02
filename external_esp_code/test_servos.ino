#include <ESP32Servo.h>

#define R_DOOR_PIN 23
#define L_DOOR_PIN 27
#define R_DOOR_SENSE_PIN 35
#define L_DOOR_SENSE_PIN 34

Servo leftdoor;
Servo rightdoor;

void doorControl(int direction)
{
  if (direction == 1)
  { // door open; moves in clockwise direction
    leftdoor.write(45);
    rightdoor.write(45);
    delay(5000); // rotates for 5 seconds
    leftdoor.write(90);
    rightdoor.write(90); // stops
  }
  else if (direction == -1)
  { // door close; moves in anticlockwise direction
    leftdoor.write(135);
    rightdoor.write(135);
    delay(5000); // rotates for 5 seconds
    leftdoor.write(90); // stops
    rightdoor.write(90);
  }
}

void setup(){
  pinMode(L_DOOR_SENSE_PIN, INPUT);
  pinMode(R_DOOR_SENSE_PIN, INPUT);
  leftdoor.attach(L_DOOR_PIN);
  rightdoor.attach(R_DOOR_PIN);

  doorControl(1);
  delay(2000);
  doorControl(-1);
}

void loop(){

}