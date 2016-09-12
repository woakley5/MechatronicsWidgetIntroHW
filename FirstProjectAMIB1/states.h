#pragma once

#include <Manager.h>

namespace IDLE {

__attribute__((weak)) void setup();
__attribute__((weak)) void enter();
__attribute__((weak)) void loop();
void event(uint8_t);
__attribute__((weak)) void exit();



namespace events {

}
}

namespace MOTIONMACHINE {
extern Value<uint32_t> stepperPosition;

__attribute__((weak)) void setup();
__attribute__((weak)) void enter();
__attribute__((weak)) void loop();
void event(uint8_t);
__attribute__((weak)) void exit();



namespace events {
void moveLiftUp();
void moveToBottom();
void setLiftToZero();
void runSteps();
void stopSteps();
}
}

namespace ARM {
extern Value<uint32_t> rotations;

__attribute__((weak)) void setup();
__attribute__((weak)) void enter();
__attribute__((weak)) void loop();
void event(uint8_t);
__attribute__((weak)) void exit();

namespace tablet {

namespace events {
void finishedAction();

}
}

namespace events {
void moveFromTallToShort();
void moveFromShortToTall();
void disableElectromagnet();
void enableElectromagnet();
void lowerArm();
void raiseArm();
void resetArmPosition();
void moveArm();
}
}



enum State {
  STATE_IDLE,
  STATE_MOTIONMACHINE,
  STATE_ARM
};

extern MasterManager<State, 3, 2> manager;
