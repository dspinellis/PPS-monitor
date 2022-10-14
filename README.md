# PPS-monitor

The PPS monitor is a Python script that will monitor a PPS
(Punkt-zu-Punkt Schnittstelle) or H-Bus heating automation network link
using a Raspberry Pi.
The script can output individual messages, or it can produce a CSV log
of all 11 monitored values.
It can also act as a [Netdata](https://github.com/firehol/netdata/) plugin.
The hardware required for hooking up to the PPS link can be found
[here](https://github.com/fredlcore/bsb_lan).
It has been tested with a Siemens RVP-210 heating controller and a QAW-70
room unit.

The program will monitor the following values.

* Set default room temperature
* Set absent room temperature
* Set domestic hot water (DHW) temperature
* Set room temperature
* Actual room temperature
* Outside temperature
* Actual flow temperature
* Actual DHW temperature
* Authority
* Mode
* Present
* Remaining absence days

## Usage
```
usage: ppsmon.py [-h] [-c] [-H] [-n NMESSAGE] [-N] [-o OUTPUT] [-p PORT] [-u]

PPS monitoring program

optional arguments:
  -h, --help            show this help message and exit
  -c, --csv             Output CSV records
  -H, --header          Print CSV header
  -n NMESSAGE, --nmessage NMESSAGE
                        Number of messages to process (default: infinite)
  -N, --netdata         Act as a netdata external plugin
  -o OUTPUT, --output OUTPUT
                        Specify CSV output file (default: stdout)
  -p PORT, --port PORT  Serial port to access (default: /dev/serial0)
  -u, --unknown         Show unknown telegrams
```

## Example: Process 10 messages, outputting individual messages
```
$ sudo ./ppsmon.py -n 10
Room unit:  Actual room temp: 21.7
Controller: Actual flow temp: 22.1
Room unit:  Set room temp: 19.0
Controller: Authority: remote
Room unit:  Mode: timed
```

## Example: Process 150 messages, outputting CSV records
```
$ sudo ./ppsmon.py  -n 150 -cH
time,Actual DHW temp,Actual flow temp,Actual room temp,Authority,Mode,Outside temp,Present,Set DHW temp,Set absent room temp,Set default room temp,Set room temp
1526237678,54.7,22.2,21.8,remote,timed,18.3,true,40.0,15.0,20.0,19.0
1526237698,54.6,22.2,21.8,remote,timed,18.3,true,40.0,15.0,20.0,19.0
1526237718,54.5,22.2,21.8,remote,timed,18.3,true,40.0,15.0,20.0,19.0
1526237738,54.7,22.2,21.8,remote,timed,18.3,true,40.0,15.0,20.0,19.0
1526237758,54.5,22.2,21.8,remote,timed,18.3,true,40.0,15.0,20.0,19.0
```
