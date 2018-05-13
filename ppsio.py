#!/usr/bin/env python
#
# Copyright 2018 Diomidis Spinellis
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
PSP monitoring program
"""

from __future__ import absolute_import
from __future__ import print_function
from itertools import count
import argparse
import RPi.GPIO as GPIO
from serial import Serial
from struct import unpack
import sys
from time import time

BAUD = 4800

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

def format_telegram(t):
    """Format the passed telegram"""
    r = ''
    for v in t:
        r += '%02x ' % v
    r += '(T=%s)' % get_temp(t)
    return r

def decode_telegram(t):
    """Decode the passed telegram into a message and its value.
    The values are None if the telegram is unknown"""

    room_unit_mode = ['timed', 'manual', 'off']

    if t[1] == 0x08:
        return ('Set default room temp', get_temp(t))
    elif t[1] == 0x09:
        return ('Set absent room temp', get_temp(t))
    elif t[1] == 0x0b:
        return ('Set DHW temp', get_temp(t))
    elif t[1] == 0x19:
        return ('Set room temp', get_temp(t))
    elif t[1] == 0x28:
        return ('Actual room temp', get_temp(t))
    elif t[1] == 0x29:
        return ('Outside temp', get_temp(t))
    elif t[1] == 0x2c:
        return ('Actual heating water temp', get_temp(t))
    elif t[1] == 0x2b:
        return ('Actual DHW temp', get_temp(t))
    elif t[1] == 0x48:
        return ('Authority', ('remote' if t[7] == 0 else 'controller'))
    elif t[1] == 0x49:
        return ('Mode', room_unit_mode[t[7]])
    elif t[1] == 0x49:
        return ('Mode', room_unit_mode[t[7]])
    elif t[1] == 0x4c:
        return ('Present', ('true' if t[7] else 'false'))
    elif t[1] == 0x7c:
        return ('Remaining absence days', t[7])
    else:
        return (None, None)

def decode_peer(t):
    """ Return the peer by its name, and True if the peer is known"""
    val = t[0]
    if val == 0xfd:
        return ('Room unit:', True)
    elif val == 0x1d:
        return ('Controller:', True)
    else:
        return ('0x%02x:' % val, False)

def print_csv(d):
    """Output the elements of the passed CSV record in a consistent order"""
    print(int(time()), end='')
    for key in sorted(d.iterkeys()):
        print(',' + d[key], end='')
    print()

def print_csv_header(d):
    """Output the header of the passed CSV record in a consistent order"""
    print('time', end='')
    for key in sorted(d.iterkeys()):
        print(',' + key, end='')
    print()

def monitor(port, nmessage, show_unknown, csv_output):
    """Monitor PPS traffic"""
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
        printed_csv_header = False
        for i in range(int(nmessage)) if nmessage else count():
            t = get_telegram(ser)
            known = True
            (message, value) = decode_telegram(t)
            if not value:
                known = False
            (peer, known_peer) = decode_peer(t)
            if not known_peer:
                known = False
            if known:
                if csv_output:
                    csv_record[message] = value
                    if len(csv_record) == CSV_ELEMENTS:
                        if not printed_csv_header:
                            print_csv_header(csv_record)
                            printed_csv_header = True
                        print_csv(csv_record)
                        csv_record = {}
                else:
                    print('%-11s %s: %s' % (peer, message,value))
            elif show_unknown:
                print('%-11s %s' % (peer, format_telegram(t)))
    GPIO.cleanup()

def main():
    """Program entry point"""
    parser = argparse.ArgumentParser(
        description='PPS monitoring program')
    parser.add_argument('-c', '--csv',
                        help='Output CSV records',
                        action='store_true')
    parser.add_argument('-n', '--nmessage',
                        help='Number of messages to process (default: infinite)')
    parser.add_argument('-p', '--port',
                        help='Serial port to access (default: /dev/serial0',
                        default='/dev/serial0')
    parser.add_argument('-u', '--unknown',
                        help='Show unknown telegrams',
                        action='store_true')

    args = parser.parse_args()
    monitor(args.port, args.nmessage, args.unknown, args.csv)

if __name__ == "__main__":
    main()
