# Paul Novus MVHR RS-485 interface

This program reads data from the RS-485 interface of Paul Novus MVHR units. It can be run on any windows or linux machine including RPI. 

The protocol was reversed engineered with extensive help of external resources listed in the https://github.com/oversc0re/paul_novus_hass/wiki together with protocol details decoded so far. 

## Hardware required
Any USB-RS485 converter should do. I am using a converter from Aliexpress for $3.

## Features
Currently the program can read:
- 4 system temperatures
- bypass state
- time remaining to filter exchange

It can be easily adopted to read system time, total running time and a few other values documented in protocol description. The only thing that is currently missing is fan speed level which is nowhere to be found :(

Next challenge is to login to the 485 bus (as a display) to be able to control the unit. The login procedure is partially documented but after announcing presence a response to master has to be given where contents are yet unknown.

Once control will be functional, a simple HASS interface will be developed on top. 