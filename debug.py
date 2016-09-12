#!/usr/bin/env python2
import re
import sys
import json
import time
import struct
try:
    import readline
except ImportError:
    import pyreadline as readline
import threading
from collections import OrderedDict, namedtuple
import os

import serial
import serial.tools.list_ports

State = namedtuple('State', ('name', 'id', 'devices'))
DeviceState = namedtuple('DeviceState', ('values', 'events'))

STATES = [State(name='IDLE', id=0, devices={'master': DeviceState(values={}, events=[]), 'tablet': DeviceState(values={}, events=[])}), State(name='MOTIONMACHINE', id=1, devices={'master': DeviceState(values=OrderedDict([('stepperPosition', 'uint32_t')]), events=['moveLiftUp', 'moveToBottom', 'setLiftToZero', 'runSteps', 'stopSteps']), 'tablet': DeviceState(values={}, events=[])}), State(name='ARM', id=2, devices={'master': DeviceState(values=OrderedDict([('rotations', 'uint32_t')]), events=['moveFromTallToShort', 'moveFromShortToTall', 'disableElectromagnet', 'enableElectromagnet', 'lowerArm', 'raiseArm', 'resetArmPosition', 'moveArm']), 'tablet': DeviceState(values=OrderedDict(), events=['finishedAction'])})]

if len(sys.argv) > 2:
    print >>sys.stderr, "Usage: python gen.py [serialport]"
    sys.exit(1)

def comm_error():
    print >>sys.stderr, "Communications error, exiting..."
    sys.exit(2)

INT_TY_RE = re.compile(r"^(u?)int(8|16|32)_t$")
STRUCT_SIZE_MAPPING = {
    '8': 'b',
    '16': 'h',
    '32': 'i',
}

def ty_to_struct(ty):
    if ty == 'bool':
        return '?'

    m = INT_TY_RE.match(ty)
    if m is None:
        return ValueError("bad type???")

    size = STRUCT_SIZE_MAPPING[m.group(2)]
    return '<' + (size.upper() if m.group(1) == 'u' else size)

def parse_val(ty, s):
    if ty == 'bool':
        if s in ('True', 'true'):
            return chr(1)
        elif s in ('False', 'false'):
            return chr(0)
        else:
            raise ValueError("%r is not a bool" % s)
    elif 'int' in ty:
        return struct.pack(ty_to_struct(ty), int(s))
    else:
        raise ValueError("unknown type %r" % ty)

if len(sys.argv) == 2:
    com_port = sys.argv[1]
else:
    try:
        hardware = json.load(open("hardware.json", 'rb'))
        master = min((int(name[4:]), serial) for (name, serial) in hardware['AMIBs'].items())[1]
        master_serial = master['serialNumber'].encode('utf-8')
    except (IOError, ValueError, IndexError, KeyError):
        print >>sys.stderr, "Non-existent or invalid hardware.json file"
        sys.exit(1)

    for port in serial.tools.list_ports.comports():
        if port.serial_number == master_serial:
            com_port = port.device
            break
    else:
        print >>sys.stderr, "Master AMIB not connected"
        sys.exit(2)

port = serial.Serial(com_port, 9600)

time.sleep(1)

port.write("\x05")
if port.read(1) != '\x05':
    comm_error()

its_build_id, = struct.unpack("<I", port.read(4))
my_build_id = 0x19465309
if its_build_id != my_build_id:
    print >>sys.stderr, "Mismatching build IDs: expected %#08x but got %#08x, exiting" % (my_build_id, its_build_id)
    sys.exit(3)

port.write("\x06")
if port.read(1) != '\x06':
    comm_error()

cur_state = STATES[ord(port.read(1))]

CMDS = [
    'event',
    'help',
    'state',
    'value',
    'test',
    'quit'
]

HELP_TEXT = (
    "state [name]: list or change states\n"
    "value [name] [value]: list values or change value\n"
    "event [name]: list events or send event\n"
    "test [name] [args]: run automated test\n"
    "quit: quit"
)

# Set this to True to make tests print out some additional information.
verbose_tests = True

# Automated test definitions. AutomatedTest is the base class, actual
# tests should inherit from this class and override the run_test()
# method.
class AutomatedTest(object):
    def __init__(self, name):
        self.name = name

    # Call this to run the test. Wraps test_function() with some error
    # and exception handling.
    def run_test(self, args):
        try:
            self.test_function(args)
            print self.name + ' finished'
            return True
        except Exception as e:
            print '%s failed: %s' % (self.name, e)
            return False

    # Test runner function. Override this from subclasses. |args| is a list
    # of any additional args the user passed in. If the test fails, this
    # function should raise an exception with a description of the error.
    def test_function(self, args):
        raise NotImplementedError('test_function() has not been implemented.')

# Try to load the test script in this same folder. To write tests:
#   1. Create a file named debug_tests.py.
#   2. Create test classes in debug_tests.py that inherit from AutomatedTest.
#   3. Add all test classes to a global list named TESTS.
# Generally importing modules is much preferred to executing text like this,
# but in this case we have some circular dependencies so importing won't work.
# The best solution would be to break this file into parts so we can
# cleanly import what we need everywhere, but that's a bit of work, so this
# is a quick little hack that should work instead.
try:
    execfile(os.path.join(os.path.dirname(__file__), 'debug_tests.py'))
except IOError:
    # No debug_tests.py file was found, no tests are available.
    TESTS = None

# Create one more test that just runs all tests we have.
class AllTests(AutomatedTest):
    def test_function(self, args):
        for test in TESTS:
	    # Don't run ourself or we will recurse forever.
	    if test is self:
	        continue
	    if not test.run_test(args):
	        return False

if TESTS:
    TESTS.append(AllTests('all'))

def common_prefix(possible, prefix):
    so_far = None
    for opt in possible:
        if opt.startswith(prefix):
            if so_far == None:
                so_far = opt
            else:
                # guaranteed not to get StopIteration because all possibilities must be different
                i = next(i for (i, (c1, c2)) in enumerate(zip(so_far, opt)) if c1 != c2)
                so_far = so_far[:i]
    return so_far

def complete(text, state):
    words = readline.get_line_buffer().split(' ')
    cmd, args = words[0], words[1:]

    if len(args) == 0:
        if state != 0:
            return None
        if cmd == '':
            print '\n' + HELP_TEXT
            readline.redisplay()
        else:
            for possible in CMDS:
                if possible.startswith(cmd):
                    return possible
            else:
                return None
    else:
        if cmd == 'state':
            possibilities = [st.name for st in STATES]
        elif cmd == 'value':
            if len(args) == 1:
                possibilities = cur_state.devices['master'].values
            else:
                return None
        elif cmd == 'event':
            possibilities = cur_state.devices['master'].events
        elif cmd == 'test':
            possibilities = [t.name for t in TESTS]
        else:
            return None

        remaining = [thing for thing in possibilities if thing.startswith(args[0])]
        if state < len(remaining):
            return remaining[state]
        else:
            return None

readline.set_completer(complete)
readline.parse_and_bind('tab: complete')

stdout_lock = threading.Lock()

COMM_INITIAL                   = 0
COMM_WAITING_FOR_CHANGE_STATE  = 1
COMM_WAITING_FOR_EVENT_STATE   = 2
COMM_WAITING_FOR_EVENT_EVENT   = 3
COMM_WAITING_FOR_VALUE_STATE   = 4
COMM_WAITING_FOR_VALUE_ID      = 5
COMM_WAITING_FOR_VALUE_VALUE   = 6
COMM_WAITING_FOR_DEBUG_SETTING = 7
COMM_WAITING_FOR_HEARTBEAT_ID  = 8

class RecvHandler(object):
    def __init__(self, port):
        self.state         = COMM_INITIAL
        self.port          = port
        self.buf           = []
        self.pending_value = None

    def handle(self):
        try:
            s = self.port.read(1)
        except serial.SerialException:
            return

        while s != '':
            b = ord(s)
            self.buf.append(b)
            if self.state == COMM_INITIAL:
                if b == 2:
                    self.state = COMM_WAITING_FOR_VALUE_STATE
                else:
                    # ??
                    self.state = COMM_INITIAL
                    self.buf = []
            elif self.state == COMM_WAITING_FOR_VALUE_STATE:
                self.state = COMM_WAITING_FOR_VALUE_ID
            elif self.state == COMM_WAITING_FOR_VALUE_ID:
                state = STATES[self.buf[1]]
                self.pending_value = next((name, ty) for (i, (name, ty)) in enumerate(state.devices['tablet'].values.items()) if i == self.buf[2])
                self.state = COMM_WAITING_FOR_VALUE_VALUE
            elif self.state == COMM_WAITING_FOR_VALUE_VALUE:
                name, ty = self.pending_value
                sty = ty_to_struct(ty)
                if struct.calcsize(sty) == len(self.buf) - 3:
                    stdout_lock.acquire()
                    print "\r%s = %s" % (name, struct.unpack(sty, ''.join(chr(n) for n in self.buf[3:]))[0])
                    print cur_state.name + "> " + readline.get_line_buffer(),
                    sys.stdout.flush()
                    stdout_lock.release()
                    self.state = COMM_INITIAL
                    self.buf = []
            else:
                raise ValueError("???")

            try:
                s = self.port.read(1)
            except serial.SerialException:
                return

handler = RecvHandler(port)
t = threading.Thread(target=handler.handle)
t.daemon = True
t.start()

# Functions to send values over serial. Used below and by tests.
def set_state(name):
    global cur_state
    cur_state = next(state for state in STATES if state.name == name)
    port.write('\x00' + chr(cur_state.id))

def set_value(value_name, value):
    for id, (name, ty) in enumerate(cur_state.devices['master'].values.items()):
        if name == value_name:
            break
    else:
        raise ValueError('No such value % r' % value_name)

    value = parse_val(ty, value)
    port.write('\x02' + chr(cur_state.id) + chr(id) + value)

def set_event(name):
    id = cur_state.devices['master'].events.index(name)
    port.write('\x01' + chr(cur_state.id) + chr(id))

print 'try "help" for help'
while True:
    s = raw_input(cur_state.name + "> ")
    words = s.split(' ')
    cmd, args = words[0], words[1:]

    stdout_lock.acquire()
    if cmd == '':
        stdout_lock.release()
        continue
    elif cmd == 'help':
        print HELP_TEXT
    elif cmd == 'state':
        if len(args) == 0:
            print '\n'.join(state.name for state in STATES)
        else:
            try:
	        set_state(args[0])
            except StopIteration:
                print "no state named %r" % args[0]
    elif cmd == 'value':
        if len(args) == 0:
            for name, ty in cur_state.devices['master'].values.items():
                print "%s: %s" % (name, ty)
        elif len(args) == 2:
	    try:
	        set_value(args[0], args[1])
            except ValueError as e:
                print e
                stdout_lock.release()
                continue
        else:
            print "Usage: value [name] [value]"
    elif cmd == 'event':
        if len(args) == 0:
            print '\n'.join(cur_state.devices['master'].events)
        elif len(args) == 1:
	    try:
	        set_event(args[0])
            except ValueError:
                print "No such value % r" % args[0]
        else:
            print "Usage: event [name]"
    elif cmd == 'test':
        if not TESTS:
	    print 'No tests have been defined for this console.'
	else:
            test = None
	    # Find the requested test by name. Could potentially put these in
	    # dict instead to make lookup easier, but this is simple enough.
	    if args:
	        for t in TESTS:
	            if t.name == args[0]:
	                test = t
		        break
            if test:
                test.run_test(args[1:])
	    else:
	        if args:
		    print 'No test named "%s".' % args[0],
	        print 'Options are:'
	        print '\n'.join(['  ' + t.name for t in TESTS])
    elif cmd in ('q', 'quit'):
        stdout_lock.release()
        break
    else:
        print "no such command %r" % cmd
    stdout_lock.release()

port.close()
