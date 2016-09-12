#include <MultiInterfaceBoard.h>
#include <FlexyStepper.h>
#include <RCServo.h>
#include <Manager.h>
#include "states.h"

void setup() {
  setupMultiInterfaceBoard();
  manager.debugSetup(STATE_IDLE);  
}

void loop() {
  manager.loop();
}