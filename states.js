
var IDLE = {
  id: 0,
  master: {
    values: {
      
    },
    events: {
      
    }
  },
  tablet: {
    values: {
      
    },
    events: {
      
    }
  }
};
var STATE_IDLE = 0;
var MOTIONMACHINE = {
  id: 1,
  master: {
    values: {
      stepperPosition: new HardwareValue(1, 0, Manager.TYPE_UINT32)
    },
    events: {
      moveLiftUp: function moveLiftUp() { manager.sendEvent(0, 1); },
      moveToBottom: function moveToBottom() { manager.sendEvent(1, 1); },
      setLiftToZero: function setLiftToZero() { manager.sendEvent(2, 1); },
      runSteps: function runSteps() { manager.sendEvent(3, 1); },
      stopSteps: function stopSteps() { manager.sendEvent(4, 1); }
    }
  },
  tablet: {
    values: {
      
    },
    events: {
      finishedAction: new LocalEvent(1, 0)
    }
  }
};
var STATE_MOTIONMACHINE = 1;
var ARM = {
  id: 2,
  master: {
    values: {
      rotations: new HardwareValue(2, 0, Manager.TYPE_UINT32)
    },
    events: {
      moveFromTallToShort: function moveFromTallToShort() { manager.sendEvent(0, 2); },
      moveFromShortToTall: function moveFromShortToTall() { manager.sendEvent(1, 2); },
      disableElectromagnet: function disableElectromagnet() { manager.sendEvent(2, 2); },
      enableElectromagnet: function enableElectromagnet() { manager.sendEvent(3, 2); },
      lowerArm: function lowerArm() { manager.sendEvent(4, 2); },
      raiseArm: function raiseArm() { manager.sendEvent(5, 2); },
      resetArmPosition: function resetArmPosition() { manager.sendEvent(6, 2); },
      moveArm: function moveArm() { manager.sendEvent(7, 2); }
    }
  },
  tablet: {
    values: {
      
    },
    events: {
      finishedAction: new LocalEvent(2, 0)
    }
  }
};
var STATE_ARM = 2;

var STATES = {
  IDLE: IDLE,
  MOTIONMACHINE: MOTIONMACHINE,
  ARM: ARM
};
var manager = new Manager([IDLE, MOTIONMACHINE, ARM]);
