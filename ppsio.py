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
import argparse
import re
import RPi.GPIO as GPIO
import serial
import struct
import sys

BAUD = 4800

def get_telegram(ser):
    """Receive a telegram sequence, terminated by more than one char time"""
    t = []
    while True:
        b = ser.read()
        if b:
            v = struct.unpack('B', b)[0]
            t.append(v)
        else:
            if t:
                return t

def monitor(port):
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
        while True:
            t = get_telegram(ser)
            for v in t:
                print('%02x ' % v, end=("\n" if v == 0x17 else ''))
            print()
    GPIO.cleanup()

def main():
    """Program entry point"""
    parser = argparse.ArgumentParser(
        description='Generic Python program')
    parser.add_argument('-p', '--port',
                        help='Serial port (/dev/serial0 by default)',
                        action='store_true')

    args = parser.parse_args()
    if args.port:
        port = args.port
    else:
        port = '/dev/serial0'
    monitor(port)

if __name__ == "__main__":
    main()
