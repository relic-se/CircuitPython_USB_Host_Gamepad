# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: Unlicense
import time
import usb_host_gamepad

DEBUG = True

# create gamepad objects for ports 1 and 2
gamepads = [usb_host_gamepad.Gamepad(i+1, debug=DEBUG) for i in range(2)]

while True:
    for i, gamepad in enumerate(gamepads):
        for event in gamepad.events:
            print(f"Port #{i}:", event)
    time.sleep(1/30)
