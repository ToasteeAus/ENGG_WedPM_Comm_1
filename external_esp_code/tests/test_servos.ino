#include <ESP32Servo.h>
#include <Wire.h>
#include <RCWL_1X05.h>

// Door Pin Definitions
#define R_DOOR_PIN 23
#define L_DOOR_PIN 27

// Class Object Constructors

Servo leftdoor;
Servo rightdoor;

// Hardware Functions //

void setupDoorServos(){
  leftdoor.attach(L_DOOR_PIN);
  rightdoor.attach(R_DOOR_PIN);
}

void doorControl(int dir)
{
  int direction = dir;

  if (direction == 1)
  { // door open; moves in clockwise direction
    leftdoor.write(45);
    delay(950);
    leftdoor.write(90);
  }
  else if (direction == -1)
  { // door close; moves in anticlockwise direction
    leftdoor.write(135);
    delay(950);
    leftdoor.write(90);
  }
}

void doorsOpen(){
  int direction = 1;
  // Currently these functions, "work" but Servos have not been ensured to still be behaving properly
  doorControl(direction);
  Serial.println("Doors Open Command");
}

void doorsClose(){
  int direction = -1;

  doorControl(direction);

  Serial.println("Doors Close Command");
}


void setup() {
  Serial.begin(115200);
  setupDoorServos();

  delay(2000);
  doorsOpen();
  delay(2000);
  doorsClose();
}

void loop() {
  
}