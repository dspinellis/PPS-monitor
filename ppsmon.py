#!/usr/bin/env python3
#
# Copyright 2018-2022 Diomidis Spinellis
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
PPS/H-Bus monitoring program
"""

import argparse
import os
from itertools import count
import RPi.GPIO as GPIO
from serial import Serial
from struct import unpack
import sys
from time import time

BAUD = 4800

# Netdata update interval. This is the time actually taken to refresh an
# entire record
update_every = 20

def get_raw_telegram(ser):
    """Receive a telegram sequence, terminated by more than one char time"""
    t = []
    while True:
        b = ser.read()
        if b:
            v = unpack('B', b)[0]
            t.append(v)
            if t == [0x17]:
                return t
        else:
            if t:
                return t

def crc(t):
    """Calculate a telegram's CRC"""
    sum = 0
    for v in t:
        sum += v
    sum &= 0xff
    return 0xff - sum + 1

def get_telegram(ser):
    """ Return a full verified telegram"""
    while True:
        t = get_raw_telegram(ser)
        if len(t) == 9:
            if crc(t[:-1]) == t[-1]:
                return t[:-1]
            else:
                sys.stderr.write("CRC error in received telegram\n")
        elif len(t) != 1:
                sys.stderr.write("Invalid telegram length %d\n" % len(t))

def get_temp(t):
    """Return the temperature associated with a telegram as a string"""
    return '%.1f' % (((t[6] << 8) + t[7]) / 64.)

def get_raw_temp(t):
    """Return the temperature associated with a telegram as an integer
    multiplied by 64"""
    return ((t[6] << 8) + t[7])

def format_telegram(t):
    """Format the passed telegram"""
    r = ''
    for v in t:
        r += '%02x ' % v
    r += '(T=%s)' % get_temp(t)
    return r

def valid_temp(t):
    """Return true if the telegram's temperature is valid"""
    return not (t[6] == 0x80 and t[7] == 0x01)

def decode_telegram(t):
    """Decode the passed telegram into a message and its formatted and
    raw value.
    The values are None if the telegram is unknown"""

    room_unit_mode = ['timed', 'manual', 'off']

    if t[1] == 0x08:
        return ('Set present room temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x09:
        return ('Set absent room temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x0b:
        return ('Set DHW temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x19:
        return ('Set room temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x28:
        return ('Actual room temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x29:
        return ('Outside temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x2c and  valid_temp(t):
        return ('Actual flow temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x2b:
        return ('Actual DHW temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x2e and  valid_temp(t):
        return ('Actual boiler temp', get_temp(t), get_raw_temp(t))
    elif t[1] == 0x48:
        return ('Authority', ('remote' if t[7] == 0 else 'controller'), t[7])
    elif t[1] == 0x49:
        return ('Mode', room_unit_mode[t[7]], t[7])
    elif t[1] == 0x4c:
        return ('Present', ('true' if t[7] else 'false'), t[7])
    elif t[1] == 0x7c:
        return ('Remaining absence days', t[7], t[7])
    else:
        return (None, None, None)

def decode_peer(t):
    """ Return the peer by its name, and True if the peer is known"""
    val = t[0]
    if val == 0xfd:
        return ('Room unit:', True)
    elif val == 0x1d:
        return ('Controller:', True)
    else:
        return ('0x%02x:' % val, False)

def print_csv(out, d):
    """Output the elements of the passed CSV record in a consistent order"""
    out.write(str(int(time())))
    for key in sorted(d):
        out.write(',' + d[key])
    out.write("\n")

def print_csv_header(out, d):
    """Output the header of the passed CSV record in a consistent order"""
    out.write('time')
    for key in sorted(d):
        out.write(',' + key)
    out.write("\n")

def monitor(port, nmessage, show_unknown, show_raw, out, csv_output,
            header_output, netdata_output):
    """Monitor PPS traffic"""
    global update_every

    CSV_ELEMENTS = 11   # Number of elements per CSV record
    NBITS = 10 # * bits plus start and stop
    CPS = BAUD / NBITS
    # Timeout if nothing received for ten characters
    TIMEOUT = 1. / CPS * 10


    # Setup 3.3V on pin 12, as required by the circuit board
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(12, GPIO.OUT, initial=GPIO.HIGH)

    with Serial(port, BAUD, timeout=TIMEOUT) as ser:
        csv_record = {}
        raw_record = {}
        last_run = dt_since_last_run = 0
        for i in range(int(nmessage)) if nmessage else count():
            t = get_telegram(ser)
            known = True
            (message, value, raw) = decode_telegram(t)
            if not value:
                known = False
            (peer, known_peer) = decode_peer(t)
            if not known_peer:
                known = False
            if known:
                if csv_output:
                    csv_record[message] = value
                    raw_record[message] = raw
                    if len(csv_record) == CSV_ELEMENTS:
                        if header_output:
                            print_csv_header(out, csv_record)
                            header_output = False
                        print_csv(out, csv_record)
                        csv_record = {}
                else:
                    out.write("%-11s %s: %s\n" % (peer, message, value))
                    if show_raw:
                        out.write("%-11s %s\n" % (peer, format_telegram(t)))
                if netdata_output:
                    raw_record[message] = raw
                    # Gather telegrams until update_every has lapsed
                    # https://github.com/firehol/netdata/wiki/External-Plugins
                    now = time()
                    if last_run > 0:
                        dt_since_last_run = now - last_run
                    if len(raw_record) == CSV_ELEMENTS and (last_run == 0 or
                            dt_since_last_run >= update_every):
                        netdata_set_values(raw_record, dt_since_last_run)
                        raw_record = {}
                        last_run = now
            elif show_unknown:
                out.write("%-11s %s\n" % (peer, format_telegram(t)))
    GPIO.cleanup()

def netdata_set_values(r, dt):
    """Output the values of a completed record"""

    # Express dt in integer microseconds
    dt = int(dt * 1e6)

    print('BEGIN Heating.ambient %d' % dt)
    print('SET t_room_set = %d' % r['Set room temp'])
    print('SET t_room_actual = %d' % r['Actual room temp'])
    print('SET t_outside = %d' % r['Outside temp'])
    print('END')

    print('BEGIN Heating.dhw %d' % dt)
    print('SET t_dhw_set = %d' % r['Set DHW temp'])
    print('SET t_dhw_actual = %d' % r['Actual DHW temp'])
    print('END')

    if 'Actual flow temp' in r:
        print('BEGIN Heating.flow %d' % dt)
        print('SET t_heating = %d' % r['Actual flow temp'])
        print('END')

    if 'Actual boiler temp' in r:
        print('BEGIN Heating.boiler %d' % dt)
        print('SET t_boiler = %d' % r['Actual boiler temp'])
        print('END')

    print('BEGIN Heating.set_point %d' % dt)
    print('SET t_present = %d' % r['Set present room temp'])
    print('SET t_absent = %d' % r['Set absent room temp'])
    print('END')

    print('BEGIN Heating.present %d' % dt)
    print('SET present = %d' % r['Present'])
    print('END')

    print('BEGIN Heating.mode %d' % dt)
    print('SET mode = %d' % r['Mode'])
    print('END')

    print('BEGIN Heating.authority %d' % dt)
    print('SET authority = %d' % r['Authority'])
    print('END')
    sys.stdout.flush()

def netdata_configure():
    """Configure the supported Netdata charts"""
    sys.stdout.write("""
CHART Heating.ambient 'Ambient T' 'Ambient temperature' 'Celsius' Temperatures Heating line 110
DIMENSION t_room_set 'Set room temperature' absolute 1 64
DIMENSION t_room_actual 'Actual room temperature' absolute 1 64
DIMENSION t_outside 'Outside temperature' absolute 1 64

CHART Heating.dhw 'Domestic hot water T' 'DHW temperature' 'Celsius' Temperatures Heating line 120
DIMENSION t_dhw_set 'Set DHW temperature' absolute 1 64
DIMENSION t_dhw_actual 'Actual DHW temperature' absolute 1 64

CHART Heating.flow 'Heating water T' 'Heating temperature' 'Celsius' Temperatures Heating line 130
DIMENSION t_heating 'Heating temperature' absolute 1 64

CHART Heating.boiler 'Boiler T' 'Boiler temperature' 'Celsius' Temperatures Heating line 135
DIMENSION t_boiler 'Heating temperature' absolute 1 64

CHART Heating.set_point 'Set temperatures' 'Set temperatures' 'Celsius' Temperatures Heating line 140
DIMENSION t_present 'Present room temperature' absolute 1 64
DIMENSION t_absent 'Absent room temperature' absolute 1 64

CHART Heating.present 'Present' 'Present' 'False/True' Control Heating line 150
DIMENSION present 'Present' absolute

CHART Heating.authority 'Authority' 'Authority' 'Remote/Controller' Control Heating line 160
DIMENSION authority 'Authority' absolute

CHART Heating.mode 'Mode' 'Mode' 'Timed/Manual/Off' Control Heating line 170
DIMENSION mode 'Mode' 'Mode' 'Timed/Manual/Off'
""")

def main():
    """Program entry point"""

    global update_every

    # Remove any Netdata-supplied update_every argument
    if 'NETDATA_UPDATE_EVERY' in os.environ:
        update_every = int(sys.argv[1])
        del sys.argv[1]

    parser = argparse.ArgumentParser(
        description='PPS monitoring program')
    parser.add_argument('-c', '--csv',
                        help='Output CSV records',
                        action='store_true')
    parser.add_argument('-H', '--header',
                        help='Print CSV header',
                        action='store_true')
    parser.add_argument('-n', '--nmessage',
                        help='Number of messages to process (default: infinite)')
    parser.add_argument('-N', '--netdata',
                        help='Act as a netdata external plugin',
                        action='store_true')
    parser.add_argument('-o', '--output',
                        help='Specify CSV output file (default: stdout)')
    parser.add_argument('-p', '--port',
                        help='Serial port to access (default: /dev/serial0)',
                        default='/dev/serial0')
    parser.add_argument('-r', '--raw',
                        help='Show telegrams also in raw format',
                        action='store_true')
    parser.add_argument('-u', '--unknown',
                        help='Show unknown telegrams',
                        action='store_true')

    args = parser.parse_args()
    if args.output:
        out = open(args.output, 'a')
    else:
        out = sys.stdout
    if args.netdata:
        netdata_configure()
    monitor(args.port, args.nmessage, args.unknown, args.raw, out, args.csv,
            args.header, args.netdata)

if __name__ == "__main__":
    main()
