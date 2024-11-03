#include <Wire.h>
#include <Arduino.h>

// Motor Pin Definitions
#define DIS_PIN 15
#define DIR_PIN 13
#define PWM_PIN 12

// Motor Speeds
int fast_speed = 225;
int slow_speed = 75;
int target_speed = 0;
int curr_speed = 0;
int speed_interval = 25;

// Test Check
int has_test_started = 0;

void setupMotorPins(){
  pinMode(DIS_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(PWM_PIN, OUTPUT);
}

void setMotorDirection(int disable, int direction){
  if(disable == 1){
    digitalWrite(DIS_PIN, HIGH);
  } else if (disable == 0) {
    digitalWrite(DIS_PIN, LOW);
  }

  if(direction == 1){
    digitalWrite(DIR_PIN, HIGH); // SHOULD BE LOW ON PRIOR to V2 BR
  } else if (direction == 0){
    digitalWrite(DIR_PIN, LOW); // SHOULD BE HIGH ON PRIOR TO V2 BR
  }

  // THE ABOVE IS FLIPPED DUE TO A POLARITY MISMATCH ON THE CURRENT MODEL
}

void runMotor(int speed){
  analogWrite(PWM_PIN, speed);
}

void set_target_speed(int newSpeed){
  target_speed = newSpeed;
}

void drive_motor(){
    if (curr_speed != target_speed){
        int temp_speed;
        
        if (target_speed < curr_speed){
        temp_speed = curr_speed - speed_interval;
        } else if (target_speed > curr_speed){
        temp_speed = curr_speed + speed_interval;
        }

        temp_speed = constrain(temp_speed, 0, fast_speed);
        runMotor(temp_speed);
        curr_speed = temp_speed;
    } else if (curr_speed == target_speed){
        Serial.println("Completion time:" + micros());
    }
}

void test_campaign(){
  curr_speed = 0; // Modify for Deceleration tests
  target_speed = 255; // Modify as required
  Serial.println("Start time:" + micros());
}

void setup(){
  Serial.begin(115200);
  setupMotorPins();
  setMotorDirection(1, 1); // Test reseting the motor direction
}

void loop(){
  if (has_test_started == 0){
      test_campaign();
      has_test_started = 1;
  }

  // Drive our Motors to check or meet the newest speed - important to do this after collision detection in case of positive hit
  drive_motor();
}