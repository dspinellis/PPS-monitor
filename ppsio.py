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

RE_INTEGER = re.compile(r'(\d+)')

def monitor(port):
    """Monitor PPS traffic"""

    # Start of frame bytes

    # Setup 3.3V on pin 12, as required by the circuit board
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(12, GPIO.OUT, initial=GPIO.HIGH)

    SOF = [0x17, 0x1d, 0x1e]
    with serial.Serial(port, 4800) as ser:
        while True:
            b = ser.read()
            v = struct.unpack('B', b)[0]
            if v in SOF:
                print()
            print('%02x ' % v, end='')
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
