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

def print_telegram(t):
    for v in t:
        print('%02x ' % v, end='')
    print()


def monitor(port, nvalues):
    """Monitor PPS traffic"""
    NBITS = 10 # * bits plus start and stop
    CPS = BAUD / NBITS
    # Timeout if nothing received for ten characters
    TIMEOUT = 1. / CPS * 10

    # Start of frame bytes
    SOF = [0x17, 0x1d, 0x1e]

    # Setup 3.3V on pin 12, as required by the circuit board
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(12, GPIO.OUT, initial=GPIO.HIGH)

    with serial.Serial(port, BAUD, timeout=TIMEOUT) as ser:
        for i in range(int(nvalues)) if nvalues else count():
            t = get_telegram(ser)
            if t[0] == 0xfd:
                print('Room unit:  ', end='')
            elif t[0] == 0x1d:
                print('Controller: ', end='')
            else:
                print('From %02x: ' % t[0], end='')
            if t[1] == 0x08:
                print('Default room temp=%.1f' % get_temp(t))
            elif t[1] == 0x09:
                print('Set absent room temp=%.1f' % get_temp(t))
            elif t[1] == 0x0b:
                print('Set DHW temp=%.1f' % get_temp(t))
            elif t[1] == 0x0e:
                print('Set Vorlauf ? temp=%.1f' % get_temp(t))
            elif t[1] == 0x19:
                print('Set room temp=%.1f' % get_temp(t))
            elif t[1] == 0x1e:
                print('Set DHW ? temp=%.1f' % get_temp(t))
            elif t[1] == 0x28:
                print('Room temp=%.1f' % get_temp(t))
            elif t[1] == 0x29:
                print('Outside temp=%.1f' % get_temp(t))
            elif t[1] == 0x2c:
                print('Heating water temp=%.1f' % get_temp(t))
            elif t[1] == 0x2b:
                print('Actual DHW temp=%.1f' % get_temp(t))
            elif t[1] == 0x4c:
                print('Present %s' % ('true' if t[7] else 'false'))
            elif t[1] == 0x57:
                print('Actual Vorlauf temp=%.1f' % get_temp(t))
            else:
                print('T=%10.1f ' % get_temp(t), end='')
                print_telegram(t)
    GPIO.cleanup()

def main():
    """Program entry point"""
    parser = argparse.ArgumentParser(
        description='Generic Python program')
    parser.add_argument('-p', '--port',
                        help='Serial port', default='/dev/serial0')
    parser.add_argument('-n', '--nvalues',
                        help='Number of values to log (default: infinite)')

    args = parser.parse_args()
    monitor(args.port, args.nvalues)

if __name__ == "__main__":
    main()
