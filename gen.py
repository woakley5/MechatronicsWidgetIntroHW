import re
import ast
from collections import defaultdict, namedtuple, OrderedDict

DeviceState = namedtuple('DeviceState', ('values', 'events'))

def parse_one(body):
    values = OrderedDict()
    events = []

    for thing in body:
        if isinstance(thing, ast.Pass):
            continue
        if not isinstance(thing, ast.FunctionDef):
            raise ValueError("must have only def's in a tablet/hardware defns")

        if thing.name == 'values':
            for stmt in thing.body:
                if isinstance(stmt, ast.Pass):
                    continue
                if not isinstance(stmt, ast.Assign):
                    raise ValueError("must have only assignments in values")

                target = stmt.targets[0]
                if not isinstance(target, ast.Name):
                    raise ValueError("value must have name")
                if not isinstance(stmt.value, ast.Name):
                    raise ValueError("value type must be a name")

                name = target.id
                ty = stmt.value.id

                if name in values:
                    raise ValueError("value name %s already used" % name)

                values[name] = ty

        if thing.name == 'events':
            for stmt in thing.body:
                if isinstance(stmt, ast.Pass):
                    continue
                if not isinstance(stmt, ast.Expr):
                    raise ValueError("must have only expressions in events")

                if not isinstance(stmt.value, ast.Name):
                    raise ValueError("event must only be name")

                name = stmt.value.id

                if name in events:
                    raise ValueError("event name %s already used" % name)

                events.append(name)

    return DeviceState(values, events)

def parse(fname):
    mod = ast.parse(open(fname, 'rb').read(), filename=fname)
    states = OrderedDict()
    device_names = set()
    for state in mod.body:
        if not isinstance(state, ast.ClassDef):
            raise ValueError("all top-level elements must be states")

        devices = defaultdict(lambda: DeviceState({}, []))

        for stmt in state.body:
            if isinstance(stmt, ast.Pass):
                continue
            if not isinstance(stmt, ast.FunctionDef):
                raise ValueError("must have functions only inside states")

            if stmt.name in ('tablet', 'master') or \
               re.match(r"amib\d+", stmt.name) is not None:
                if stmt.name in devices:
                    raise ValueError("value/events for %r defined more than once" % stmt.name)

                device_names.add(stmt.name)
                devices[stmt.name] = parse_one(stmt.body)
            else:
                raise ValueError("can't define any things other than tablet and hardware")

        states[state.name] = devices

    return device_names, states

MASTER_HEADER_TEMPLATE = """#pragma once

#include <Manager.h>

{namespaces}

enum State {{
  {states}
}};

extern MasterManager<State, {num_states}, {num_values}> manager;
"""

MASTER_NAMESPACE_TEMPLATE = """namespace {name} {{
{values}
__attribute__((weak)) void setup();
__attribute__((weak)) void enter();
__attribute__((weak)) void loop();
void event(uint8_t);
__attribute__((weak)) void exit();

{remotes}

namespace events {{
{events}
}}
}}

"""

MASTER_REMOTE = """namespace {name} {{
{values}
namespace events {{
{events}
}}
}}"""
MASTER_REMOTE_VALUE_TEMPLATE = """extern RemoteValue<{slave_id}, {type}> {name};"""
MASTER_REMOTE_EVENT_TEMPLATE = """void {name}();
"""

MASTER_WIREVALUE_TEMPLATE = "{{{state_id}, {value_id}, {size}, (Value<void*>*) &{state}::{name}}}"
MASTER_STATEINFO_TEMPLATE = "{{{state}::setup, {state}::enter, {state}::exit, {state}::loop, {state}::event}}"
MASTER_VALUE_TEMPLATE = "extern Value<{type}> {name};\n"
MASTER_EVENT_TEMPLATE = "void {name}();"

MASTER_SOURCE_TEMPLATE = """#include "states.h"

static const StateInfo state_infos[{num_states}] = {{
  {state_infos}
}};

static const WireValue wire_values[{num_values}] = {{
  {wire_values}
}};

MasterManager<State, {num_states}, {num_values}> manager({build_id:#08x}, state_infos, wire_values, {slaves});

{states_code}
"""
MASTER_SOURCE_STATE = """namespace {name} {{
{hardware_values}

void event(uint8_t ev) {{
  switch (ev) {{
  {cases}
  default:
    break;
  }}
}}

{remotes}
}}
"""
MASTER_SOURCE_CASE = """case {id}:
    events::{name}();
    break;"""

MASTER_SOURCE_REMOTE = """namespace {name} {{
{values}
namespace events {{
{events}
}}
}}"""
MASTER_SOURCE_REMOTE_VALUE = "RemoteValue<{remote_id}, {type}> {name}({id});"
MASTER_SOURCE_TABLET_EVENT = "void {name}() {{ manager.sendTabletEvent({id}); }}"
MASTER_SOURCE_REMOTE_EVENT = "void {name}() {{ manager.sendSlaveEvent({slave_id}, {id}); }}"
MASTER_SOURCE_VALUE = "Value<{type}> {name};"

def generate_master(master_name, states, build_id, slaves):
    namespaces = ''.join(
        MASTER_NAMESPACE_TEMPLATE.format(
            name=name,
            values=''.join(MASTER_VALUE_TEMPLATE.format(name=name, type=ty) for (name, ty) in devices['master'].values.items()),
            events='\n'.join(MASTER_EVENT_TEMPLATE.format(name=name) for name in devices['master'].events),
            remotes='\n'.join(MASTER_REMOTE.format(name=remote_name, values='\n'.join(MASTER_REMOTE_VALUE_TEMPLATE.format(slave_id=int(remote_name[4:]) if remote_name != 'tablet' else 0, type=ty, name=name) for (name, ty) in device.values.items()), events='\n'.join(MASTER_REMOTE_EVENT_TEMPLATE.format(name=name) for name in device.events)) for (remote_name, device) in devices.items() if remote_name != master_name)
        )
        for (name, devices)
        in states.items()
    )
    states_str = ',\n  '.join('STATE_' + name for name in states)
    num_values = sum(len(devices['master'].values) for devices in states.values())
    header = MASTER_HEADER_TEMPLATE.format(states=states_str,
                                      num_states=len(states),
                                      num_values=num_values,
                                      namespaces=namespaces)


    states_code = ''.join(
        MASTER_SOURCE_STATE.format(
            name=name,
            hardware_values='\n'.join(MASTER_SOURCE_VALUE.format(name=name, type=ty) for (name, ty) in devices['master'].values.items()),
            cases='\n  '.join(MASTER_SOURCE_CASE.format(name=name, id=i) for (i, name) in enumerate(devices['master'].events)),
            remotes='\n'.join(MASTER_SOURCE_REMOTE.format(name=remote_name, values='\n'.join(MASTER_SOURCE_REMOTE_VALUE.format(remote_id=int(remote_name[4:]) if remote_name != 'tablet' else 0, type=ty, name=name, id=i) for (i, (name, ty)) in enumerate(device.values.items())), events='\n'.join((MASTER_SOURCE_TABLET_EVENT if remote_name == 'tablet' else MASTER_SOURCE_REMOTE_EVENT).format(slave_id=remote_name[4:], id=i, name=name) for (i, name) in enumerate(device.events))) for (remote_name, device) in devices.items() if remote_name != master_name)
        )
        for (name, devices)
        in states.items()
    )
    state_infos = ',\n  '.join(MASTER_STATEINFO_TEMPLATE.format(state=state) for state in states)
    wire_values = ',\n  '.join(MASTER_WIREVALUE_TEMPLATE.format(
        state=state,
        state_id=state_i,
        name=value,
        value_id=value_i,
        size='sizeof({})'.format(ty),
    ) for (state_i, (state, devices)) in enumerate(states.items())
      for (value_i, (value, ty)) in enumerate(devices['master'].values.items()))
    source = MASTER_SOURCE_TEMPLATE.format(
        build_id=build_id,
        num_states=len(states),
        num_values=num_values,
        state_infos=state_infos,
        wire_values=wire_values,
        states_code=states_code,
        slaves=slaves
    )

    return header, source

# TODO: reduce code duplication between sub and master
SUB_HEADER_TEMPLATE = """#pragma once

#define SLAVEMANAGER
#include <Manager.h>

{namespaces}

enum State {{
  {states}
}};

extern SlaveManager<State, {num_states}, {num_values}> manager;
"""

SUB_NAMESPACE_TEMPLATE = """namespace {name} {{
{values}
__attribute__((weak)) void setup();
__attribute__((weak)) void enter();
__attribute__((weak)) void loop();
void event(uint8_t);
__attribute__((weak)) void exit();

namespace events {{
{events}
}}

namespace master {{
{master_values}

namespace events {{
{master_events}
}}
}}
}}

"""

SUB_MASTER_VALUE_TEMPLATE = """extern RemoteValue<0, {type}> {name};"""
SUB_MASTER_EVENT_TEMPLATE = """void {name}();"""

SUB_WIREVALUE_TEMPLATE = "{{{state_id}, {value_id}, {size}, (Value<void*>*) &{state}::{name}}}"
SUB_STATEINFO_TEMPLATE = "{{{state}::setup, {state}::enter, {state}::exit, {state}::loop, {state}::event}}"
SUB_VALUE_TEMPLATE = "extern Value<{type}> {name};\n"
SUB_EVENT_TEMPLATE = "void {name}();"

SUB_SOURCE_TEMPLATE = """#include <SerialSlave.h>
#include "states.h"

static const StateInfo state_infos[{num_states}] = {{
  {state_infos}
}};

static const WireValue wire_values[{num_values}] = {{
  {wire_values}
}};

SlaveManager<State, {num_states}, {num_values}> manager({amib_number}, state_infos, wire_values);

{states_code}

SLAVERECV
"""
SUB_SOURCE_STATE = """namespace {name} {{
{hardware_values}

void event(uint8_t ev) {{
  switch (ev) {{
  {cases}
  default:
    break;
  }}
}}

namespace master {{
{master_values}

namespace events {{
{master_events}
}}
}}
}}
"""
SUB_SOURCE_CASE = """case {id}:
    events::{name}();
    break;"""
SUB_SOURCE_MASTER_VALUE = "RemoteValue<0, {type}> {name}({id});"
SUB_SOURCE_MASTER_EVENT = "void {name}() {{ manager.sendEvent({id}); }}"
SUB_SOURCE_VALUE = "Value<{type}> {name};"

def generate_sub(dname, states):
    namespaces = ''.join(
        SUB_NAMESPACE_TEMPLATE.format(
            name=name,
            values=''.join(SUB_VALUE_TEMPLATE.format(name=name, type=ty) for (name, ty) in devices[dname].values.items()),
            events='\n'.join(SUB_EVENT_TEMPLATE.format(name=name) for name in devices[dname].events),
            master_values='\n'.join(SUB_MASTER_VALUE_TEMPLATE.format(type=ty, name=name) for (name, ty) in devices['master'].values.items()),
            master_events='\n'.join(SUB_MASTER_EVENT_TEMPLATE.format(name=name) for name in devices['master'].events)
        )
        for (name, devices)
        in states.items()
    )
    states_str = ',\n  '.join('STATE_' + name for name in states)
    num_values = sum(len(devices[dname].values) for devices in states.values())
    header = SUB_HEADER_TEMPLATE.format(states=states_str,
                                      num_states=len(states),
                                      num_values=num_values,
                                      namespaces=namespaces)

    states_code = ''.join(
        SUB_SOURCE_STATE.format(
            name=name,
            hardware_values='\n'.join(SUB_SOURCE_VALUE.format(name=name, type=ty) for (name, ty) in devices[dname].values.items()),
            cases='\n  '.join(SUB_SOURCE_CASE.format(name=name, id=i) for (i, name) in enumerate(devices[dname].events)),
            master_values='\n'.join(SUB_SOURCE_MASTER_VALUE.format(type=ty, name=name, id=i) for (i, (name, ty)) in enumerate(devices['master'].values.items())),
            master_events='\n'.join(SUB_SOURCE_MASTER_EVENT.format(id=i, name=name) for (i, name) in enumerate(devices['master'].events))
        )
        for (name, devices)
        in states.items()
    )
    state_infos = ',\n  '.join(SUB_STATEINFO_TEMPLATE.format(state=state) for state in states)
    wire_values = ',\n  '.join(SUB_WIREVALUE_TEMPLATE.format(
        state=state,
        state_id=state_i,
        name=value,
        value_id=value_i,
        size='sizeof({})'.format(ty),
    ) for (state_i, (state, devices)) in enumerate(states.items())
      for (value_i, (value, ty)) in enumerate(devices[dname].values.items()))

    source = SUB_SOURCE_TEMPLATE.format(
        amib_number=int(dname[4:]),
        num_states=len(states),
        num_values=num_values,
        state_infos=state_infos,
        wire_values=wire_values,
        states_code=states_code
    )

    return header, source

TABLET_SOURCE_TEMPLATE = """
{states}
var STATES = {{
  {states_object}
}};
var manager = new Manager([{state_names}]);
"""
TABLET_STATE_TEMPLATE = """var {name} = {{
  id: {id},
  master: {{
    values: {{
      {hardware_values}
    }},
    events: {{
      {hardware_events}
    }}
  }},
  tablet: {{
    values: {{
      {tablet_values}
    }},
    events: {{
      {tablet_events}
    }}
  }}
}};
var STATE_{name} = {id};
"""
TABLET_STATE_OBJECT = "{name}: {name}"

TABLET_HARDWARE_VALUE = "{name}: new HardwareValue({state_id}, {id}, {type})"
TABLET_HARDWARE_EVENT = "{name}: function {name}() {{ manager.sendEvent({id}, {state_id}); }}"
TABLET_TABLET_VALUE = "{name}: new LocalValue({id}, {type})"
TABLET_TABLET_EVENT = "{name}: new LocalEvent({state_id}, {id})"

def c_to_js_type(ty):
    return "Manager.TYPE_" + {
        "bool": "BOOL",
        "uint8_t": "UINT8",
        "int8_t": "INT8",
        "uint16_t": "UINT16",
        "int16_t": "INT16",
        "uint32_t": "UINT32",
        "int32_t": "INT32",
    }[ty]

def generate_tablet(states, build_id):
    states_s = ""
    for state_id, (state, devices) in enumerate(states.items()):
        hw_values, hw_events = devices['master']
        t_values, t_events = devices['tablet']

        hw_values_s = ',\n      '.join(
            TABLET_HARDWARE_VALUE.format(state_id=state_id, name=name, id=i, type=c_to_js_type(ty))
            for (i, (name, ty))
            in enumerate(hw_values.items())
        )
        hw_events_s = ',\n      '.join(
            TABLET_HARDWARE_EVENT.format(name=name, id=i, state_id=state_id)
            for (i, name)
            in enumerate(hw_events)
        )

        t_values_s = ',\n      '.join(
            TABLET_TABLET_VALUE.format(name=name, id=i, type=c_to_js_type(ty))
            for (i, (name, ty))
            in enumerate(t_values.items())
        )
        t_events_s = ',\n      '.join(
            TABLET_TABLET_EVENT.format(name=name, state_id=state_id, id=i)
            for (i, name)
            in enumerate(t_events)
        )

        states_s += TABLET_STATE_TEMPLATE.format(
            name=state,
            hardware_values=hw_values_s,
            hardware_events=hw_events_s,
            tablet_values=t_values_s,
            tablet_events=t_events_s,
            id=state_id,
        )

    return TABLET_SOURCE_TEMPLATE.format(
        states=states_s,
        state_names=', '.join(states),
        states_object=',\n  '.join(TABLET_STATE_OBJECT.format(name=state) for state in states)
    )

DEBUG_SOURCE_TEMPLATE = r"""#!/usr/bin/env python2
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

STATES = {states}

if len(sys.argv) > 2:
    print >>sys.stderr, "Usage: python gen.py [serialport]"
    sys.exit(1)

def comm_error():
    print >>sys.stderr, "Communications error, exiting..."
    sys.exit(2)

INT_TY_RE = re.compile(r"^(u?)int(8|16|32)_t$")
STRUCT_SIZE_MAPPING = {{
    '8': 'b',
    '16': 'h',
    '32': 'i',
}}

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
my_build_id = {build_id:#08x}
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
"""

State = namedtuple('State', ('name', 'id', 'devices'))

def generate_debug(states, build_id):
    new_states = []
    for i, (name, state) in enumerate(states.items()):
        new_states.append(State(name, i, dict(state)))
    return DEBUG_SOURCE_TEMPLATE.format(states=new_states, build_id=build_id)

if __name__ == '__main__':
    import os
    import sys
    import json

    weird_mode = False
    if len(sys.argv) >= 4:
        if sys.argv[1] == '-w':
            sys.argv.pop(1)
            weird_mode = True

    if len(sys.argv) > 3:
        print >>sys.stderr, "Error: too many arguments"
        print >>sys.stderr, "Usage: %s Consolenn /path/to/consolenn.comm" % sys.argv[0]
        sys.exit(1)

    if len(sys.argv) == 3:
        console_name, comm_file = sys.argv[1:]
    elif len(sys.argv) == 2:
        console_name = sys.argv[1]
        comm_file = console_name + ".comm"
    else:
        try:
            hardware = json.load(open("hardware.json", 'rb'))
            console_name = hardware['name']
            comm_file = console_name + ".comm"
        except (IOError, ValueError, KeyError):
            print >>sys.stderr, "Must either have valid hardware.json or give proper arguments"
            sys.exit(1)

    device_names, states = parse(comm_file)
    device_names |= {'tablet', 'master'}
    dirname = os.path.dirname(comm_file)

    # this line is an abomination
    hashable_states = tuple((name, frozenset((devname, (frozenset(values.items()), tuple(events))) for (devname, (values, events)) in devices.items())) for (name, devices) in states.items())
    build_id = hash(hashable_states) & (2**32 - 1)
    print "Build ID: %08x" % build_id

    if weird_mode:
        js = generate_tablet(states, build_id)
        open(os.path.join(dirname, "states.js"), 'wb').write(js)

        header, source = generate_master('master', states, build_id, 0)
        open(os.path.join(dirname, "states.h"), 'wb').write(header)
        open(os.path.join(dirname, "states.cpp"), 'wb').write(source)

        debug = generate_debug(states, build_id)
        open(os.path.join(dirname, "debug.py"), 'wb').write(debug)

        sys.exit(0)

    slaves = 0
    master_name = None
    if device_names == {'master', 'tablet'}:
        master_name = 'AMIB1'
        slaves |= 0
    if 'amib2' in device_names:
        master_name = 'AMIB1'
        slaves |= 1
    if 'amib3' in device_names:
        if master_name is None:
            master_name = 'AMIB2'
        slaves |= 2
    if 'amib4' in device_names:
        if master_name is None:
            master_name = 'AMIB3'
        slaves |= 4

    for name in device_names:
        if name == 'tablet':
            js = generate_tablet(states, build_id)
            open(os.path.join(dirname, "states.js"), 'wb').write(js)
        elif name == 'master':
            header, source = generate_master('master', states, build_id, slaves)
            open(os.path.join(dirname, console_name + master_name, "states.h"), 'wb').write(header)
            open(os.path.join(dirname, console_name + master_name, "states.cpp"), 'wb').write(source)
        else:
            header, source = generate_sub(name, states)
            name = 'AMIB' + name[4:]
            open(os.path.join(dirname, console_name + name, "states.h"), 'wb').write(header)
            open(os.path.join(dirname, console_name + name, "states.cpp"), 'wb').write(source)

    debug = generate_debug(states, build_id)
    open(os.path.join(dirname, "debug.py"), 'wb').write(debug)
