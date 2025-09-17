# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: Unlicense
#
# Tested on Fruit Jam RP2350b
# Install prerequisites: circup install adafruit_fruitjam
import time

import displayio
import supervisor
import vectorio
from adafruit_fruitjam.peripherals import request_display_config

import relic_usb_host_gamepad

displayio.release_displays()

request_display_config(320, 240)
display = supervisor.runtime.display
display.auto_refresh = False

main_group = displayio.Group()
display.root_group = main_group


class Gamepad(displayio.Group):
    def __init__(self, port: int, size: int = 100):
        super().__init__()
        self._gamepad = relic_usb_host_gamepad.Gamepad(port)

        bg_palette = displayio.Palette(1)
        bg_palette[0] = 0x0000FF
        self._bg = vectorio.Rectangle(pixel_shader=bg_palette, width=size, height=int(size * 0.6))
        self.append(self._bg)

        self._released_palette = displayio.Palette(1)
        self._released_palette[0] = 0x888888

        self._pressed_palette = displayio.Palette(1)
        self._pressed_palette[0] = 0xFFFFFF

        button_size = int(size * 0.05)

        self._buttons = (
            (0.85, 0.4),  # A
            (0.8, 0.5),  # B
            (0.8, 0.3),  # X
            (0.75, 0.4),  # Y
            (0.2, 0.3),  # UP
            (0.2, 0.5),  # DOWN
            (0.15, 0.4),  # LEFT
            (0.25, 0.4),  # RIGHT
            (0.6, 0.4),  # START
            (0.4, 0.4),  # SELECT
            (0.5, 0.4),  # HOME
            (0.1, 0.1),  # L1
            (0.9, 0.1),  # R1
            (0.2, 0.1),  # L2
            (0.8, 0.1),  # R2
            (0.3, 0.1),  # L3
            (0.7, 0.1),  # R3
            (0.35, 0.6),  # JOYSTICK_UP
            (0.35, 0.9),  # JOYSTICK_DOWN
            (0.25, 0.75),  # JOYSTICK_LEFT
            (0.45, 0.75),  # JOYSTICK_RIGHT
        )
        self._circles = []
        for x, y in self._buttons:
            circle = vectorio.Circle(
                pixel_shader=self._released_palette,
                radius=button_size // 2,
                x=int(x * self.width),
                y=int(y * self.height),
            )
            self._circles.append(circle)
            self.append(circle)

        self._joystick_outer_size = int(size * 0.15)
        self._joystick_inner_size = int(size * 0.05)

        joystick_outer_palette = displayio.Palette(1)
        joystick_outer_palette[0] = 0x000000

        joystick_inner_palette = displayio.Palette(1)
        joystick_inner_palette[0] = 0xFFFFFF

        self._joysticks = (
            ("left_joystick", 0.35, 0.75),
            ("right_joystick", 0.65, 0.75),
        )
        self._joystick_circles = []
        for name, x, y in self._joysticks:
            outer = vectorio.Circle(
                pixel_shader=joystick_outer_palette,
                radius=self._joystick_outer_size // 2,
                x=int(x * self.width),
                y=int(y * self.height),
            )
            self.append(outer)
            inner = vectorio.Circle(
                pixel_shader=joystick_inner_palette,
                radius=self._joystick_inner_size // 2,
                x=int(x * self.width),
                y=int(y * self.height),
            )
            self._joystick_circles.append(inner)
            self.append(inner)

    @property
    def width(self) -> int:
        return self._bg.width

    @property
    def height(self) -> int:
        return self._bg.height

    def update(self) -> bool:
        if self._gamepad.update():
            if self._gamepad.buttons.changed:
                for event in self._gamepad.buttons.events:
                    self._circles[event.key_number].pixel_shader = (
                        self._pressed_palette if event.pressed else self._released_palette
                    )
            for i, data in enumerate(self._joysticks):
                name, x, y = data
                js_x, js_y = getattr(self._gamepad, name)
                self._joystick_circles[i].x = int(
                    (js_x * self._joystick_outer_size // 2) + (x * self.width)
                )
                self._joystick_circles[i].y = int(
                    (-js_y * self._joystick_outer_size // 2) + (y * self.height)
                )
            return True
        return False


gamepads = [Gamepad(i + 1) for i in range(2)]

gap = (display.width - sum(x.width for x in gamepads)) // (len(gamepads) + 1)
for i, gamepad in enumerate(gamepads):
    gamepad.x = gap * (i + 1) + gamepad.width * i
    gamepad.y = (display.height - gamepad.height) // 2
    main_group.append(gamepad)

# initial refresh
display.refresh()

while True:
    updated = False
    for gamepad in gamepads:
        if gamepad.update():
            updated = True
    if updated:
        display.refresh()

    time.sleep(1 / 30)
