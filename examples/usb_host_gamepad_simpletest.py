# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: Unlicense
#
# Tested on Fruit Jam RP2350b
# Install prerequisites: circup install neopixel
import board
import supervisor
import time
import usb_host_gamepad
from neopixel import NeoPixel

DEBUG = False

neopixels = NeoPixel(board.NEOPIXEL, 5)
neopixels.fill(0x000000)

# disable REPL display output for better performance
supervisor.runtime.display.root_group = None

# create gamepad objects for ports 1 and 2
gamepads = [usb_host_gamepad.Gamepad(i+1, debug=DEBUG) for i in range(2)]

while True:
    changed = False
    for i, gamepad in enumerate(gamepads):
        if gamepad.update() and gamepad.buttons.is_changed():
            changed = True
            for j, button in enumerate((gamepad.buttons.A, gamepad.buttons.B)):
                neopixels[i*len(gamepads)+j] = 0xffffff if button.pressed else 0x000000
            for button in gamepad.buttons.get_changed():
                print(button)
    if changed:
        neopixels.show()
    time.sleep(1/60)
