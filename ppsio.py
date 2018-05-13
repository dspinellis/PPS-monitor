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
Generic program
"""

from __future__ import absolute_import
from __future__ import print_function
from itertools import count
import argparse
import re
import RPi.GPIO as GPIO
import serial
import struct
import sys

BAUD = 4800

def get_raw_telegram(ser):
    """Receive a telegram sequence, terminated by more than one char time"""
    t = []
    while True:
        b = ser.read()
        if b:
            v = struct.unpack('B', b)[0]
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
    """Return the temperature associated with a telegram"""
    return ((t[6] << 8) + t[7]) / 64.

def format_telegram(t):
    """Format the passed telegram"""
    r = ''
    for v in t:
        r += '%02x ' % v
    r += '(T=%.1f)' % get_temp(t)
    return r


def monitor(port, nmessage, show_unknown):
    """Monitor PPS traffic"""
    NBITS = 10 # * bits plus start and stop
    CPS = BAUD / NBITS
    # Timeout if nothing received for ten characters
    TIMEOUT = 1. / CPS * 10

    room_unit_mode = ['Timed', 'Manual', 'Off']

    # Setup 3.3V on pin 12, as required by the circuit board
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(12, GPIO.OUT, initial=GPIO.HIGH)

    with serial.Serial(port, BAUD, timeout=TIMEOUT) as ser:
        for i in range(int(nmessage)) if nmessage else count():
            t = get_telegram(ser)
            unknown = False
            if t[0] == 0xfd:
                peer = 'Room unit:'
            elif t[0] == 0x1d:
                peer = 'Controller:'
            else:
                peer = '0x%02x:' % t[0]
                unknown = True
            if t[1] == 0x08:
                action = 'Set default room temp=%.1f' % get_temp(t)
            elif t[1] == 0x09:
                action = 'Set absent room temp=%.1f' % get_temp(t)
            elif t[1] == 0x0b:
                action = 'Set DHW temp=%.1f' % get_temp(t)
            elif t[1] == 0x19:
                action = 'Set room temp=%.1f' % get_temp(t)
            elif t[1] == 0x28:
                action = 'Actual room temp=%.1f' % get_temp(t)
            elif t[1] == 0x29:
                action = 'Outside temp=%.1f' % get_temp(t)
            elif t[1] == 0x2c:
                action = 'Actual heating water temp=%.1f' % get_temp(t)
            elif t[1] == 0x2b:
                action = 'Actual DHW temp=%.1f' % get_temp(t)
            elif t[1] == 0x48:
                action = 'Authority: %s' % ('room unit' if t[7] == 0 else 'controller')
            elif t[1] == 0x49:
                action = 'Mode: %s' % room_unit_mode[t[7]]
            elif t[1] == 0x49:
                action = 'Mode: %s' % room_unit_mode[t[7]]
            elif t[1] == 0x4c:
                action = 'Present: %s' % ('true' if t[7] else 'false')
            elif t[1] == 0x7c:
                action = 'Remaining absence days: %d' % t[7]
            else:
                action = format_telegram(t)
                unknown = True
            if not unknown or show_unknown:
                print('%-12s %s' % (peer, action))
    GPIO.cleanup()

def main():
    """Program entry point"""
    parser = argparse.ArgumentParser(
        description='PPS monitoring program')
    parser.add_argument('-n', '--nmessage',
                        help='Number of messages to process (default: infinite)')
    parser.add_argument('-p', '--port',
                        help='Serial port', default='/dev/serial0')
    parser.add_argument('-u', '--unknown',
                        help='Show unknown telegrams',
                        action='store_true')

    args = parser.parse_args()
    monitor(args.port, args.nmessage, args.unknown)

if __name__ == "__main__":
    main()
