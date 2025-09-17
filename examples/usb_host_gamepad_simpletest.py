# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: Unlicense
#
# Tested on Fruit Jam RP2350b
# Install prerequisites: circup install neopixel
import time

import board
import displayio
from neopixel import NeoPixel

import relic_usb_host_gamepad

DEBUG = False

# disable REPL display output for better performance
displayio.release_displays()

neopixels = NeoPixel(board.NEOPIXEL, 5)
neopixels.fill(0x000000)

# create gamepad objects for ports 1 and 2
gamepads = [relic_usb_host_gamepad.Gamepad(i + 1, debug=DEBUG) for i in range(2)]

while True:
    changed = False
    for i, gamepad in enumerate(gamepads):
        if gamepad.update() and gamepad.buttons.changed:
            changed = True
            for j, pressed in enumerate((gamepad.buttons.A, gamepad.buttons.B)):
                neopixels[i * len(gamepads) + j] = 0xFFFFFF if pressed else 0x000000
            for event in gamepad.buttons.events:
                print(
                    "Gamepad {:d}: {:s} {:s}".format(
                        i + 1,
                        relic_usb_host_gamepad.BUTTON_NAMES[event.key_number],
                        ("Pressed" if event.pressed else "Released"),
                    )
                )
    if changed:
        neopixels.show()
    time.sleep(1 / 60)
