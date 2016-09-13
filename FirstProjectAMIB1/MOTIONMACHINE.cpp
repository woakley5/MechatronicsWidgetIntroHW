#include <RCServo.h>
#include <SpeedyStepper.h>
#include "states.h"

namespace MOTIONMACHINE {
SpeedyStepper stepper1;
RCServo gateServo;
const byte LOWER_SENSOR = 59;
const byte UPPER_SENSOR = 60;
const byte LIMIT_SENSOR = 61;
const byte STEP_MOTOR = 4;
const byte SERVO_GATE = 58;
bool liftReady = false;
int servoClosedPosition;
int servoOpenPosition;

void setup() {
  stepper1.connectToPort(1);
  stepper1.setStepsPerMillimeter(100);
  stepper1.setSpeedInMillimetersPerSecond(25);
  stepper1.setAccelerationInMillimetersPerSecondPerSecond(10);
  stepper1.disableStepper();
  //gateServo.setServoPosition(25);
  gateServo.connectToPin(SERVO_GATE);
  pinMode(STEP_MOTOR, OUTPUT);
  pinMode(LOWER_SENSOR, INPUT_PULLUP);
  pinMode(UPPER_SENSOR, INPUT_PULLUP);
  pinMode(LIMIT_SENSOR, INPUT_PULLUP);
  servoClosedPosition = 0;
  servoOpenPosition = 0.9;
  events::setLiftToZero();
}

void loop() {

}

void events::moveLiftUp() {
  liftReady = false;
  gateServo.setServoPosition(servoClosedPosition);

  stepper1.enableStepper();
  stepper1.setupMoveInMillimeters(-226);
  while(!stepper1.motionComplete())
  {
    stepper1.processMovement();
  }
  stepper1.disableStepper();

}

void events::moveToBottom() {
  stepper1.enableStepper();
  stepper1.setupMoveInMillimeters(0);
  while(!stepper1.motionComplete())
  {
    stepper1.processMovement();
  }  
  stepper1.disableStepper();
  liftReady = true;

  gateServo.setServoPosition(servoOpenPosition);
}

void events::setLiftToZero() {
  stepper1.enableStepper();
  stepper1.moveToHomeInMillimeters(1, 50, 250, LIMIT_SENSOR);
  stepper1.setCurrentPositionInMillimeters(0);
  stepper1.disableStepper();
  liftReady = true;
  gateServo.setServoPosition(servoOpenPosition);
}

void events::runSteps(){
  digitalWrite(STEP_MOTOR, HIGH);
}
void events::stopSteps(){
  digitalWrite(STEP_MOTOR, LOW);
}
}

