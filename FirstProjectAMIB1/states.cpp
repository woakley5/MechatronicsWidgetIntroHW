#include "states.h"

static const StateInfo state_infos[3] = {
  {IDLE::setup, IDLE::enter, IDLE::exit, IDLE::loop, IDLE::event},
  {MOTIONMACHINE::setup, MOTIONMACHINE::enter, MOTIONMACHINE::exit, MOTIONMACHINE::loop, MOTIONMACHINE::event},
  {ARM::setup, ARM::enter, ARM::exit, ARM::loop, ARM::event}
};

static const WireValue wire_values[2] = {
  {1, 0, sizeof(uint32_t), (Value<void*>*) &MOTIONMACHINE::stepperPosition},
  {2, 0, sizeof(uint32_t), (Value<void*>*) &ARM::rotations}
};

MasterManager<State, 3, 2> manager(0x19465309, state_infos, wire_values, 0);

namespace IDLE {


void event(uint8_t ev) {
  switch (ev) {
  
  default:
    break;
  }
}


}
namespace MOTIONMACHINE {
Value<uint32_t> stepperPosition;

void event(uint8_t ev) {
  switch (ev) {
  case 0:
    events::moveLiftUp();
    break;
  case 1:
    events::moveToBottom();
    break;
  case 2:
    events::setLiftToZero();
    break;
  case 3:
    events::runSteps();
    break;
  case 4:
    events::stopSteps();
    break;
  default:
    break;
  }
}


}
namespace ARM {
Value<uint32_t> rotations;

void event(uint8_t ev) {
  switch (ev) {
  case 0:
    events::moveFromTallToShort();
    break;
  case 1:
    events::moveFromShortToTall();
    break;
  case 2:
    events::disableElectromagnet();
    break;
  case 3:
    events::enableElectromagnet();
    break;
  case 4:
    events::lowerArm();
    break;
  case 5:
    events::raiseArm();
    break;
  case 6:
    events::resetArmPosition();
    break;
  case 7:
    events::moveArm();
    break;
  default:
    break;
  }
}

namespace tablet {

namespace events {
void finishedAction() { manager.sendTabletEvent(0); }
}
}
}

