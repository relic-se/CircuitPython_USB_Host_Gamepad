# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: Unlicense
#
# Tested on Fruit Jam RP2350b
# Install prerequisites: circup install adafruit_fruitjam
import displayio
import supervisor
import time
import usb_host_gamepad
import vectorio
from adafruit_fruitjam.peripherals import request_display_config

displayio.release_displays()

request_display_config(320, 240)
display = supervisor.runtime.display
display.auto_refresh = False

main_group = displayio.Group()
display.root_group = main_group

class Gamepad(displayio.Group):
    def __init__(self, port:int, size:int=100):
        super().__init__()
        self._gamepad = usb_host_gamepad.Gamepad(port)

        bg_palette = displayio.Palette(1)
        bg_palette[0] = 0x0000ff
        self._bg = vectorio.Rectangle(pixel_shader=bg_palette, width=size, height=int(size*.6))
        self.append(self._bg)

        self._released_palette = displayio.Palette(1)
        self._released_palette[0] = 0x888888

        self._pressed_palette = displayio.Palette(1)
        self._pressed_palette[0] = 0xffffff

        button_size = int(size * .05)

        self._buttons = (
            (usb_host_gamepad.Button.A,              .85, .4 ),
            (usb_host_gamepad.Button.B,              .8,  .5 ),
            (usb_host_gamepad.Button.X,              .8,  .3 ),
            (usb_host_gamepad.Button.Y,              .75, .4 ),
            (usb_host_gamepad.Button.LEFT,           .15, .4 ),
            (usb_host_gamepad.Button.RIGHT,          .25, .4 ),
            (usb_host_gamepad.Button.UP,             .2,  .3 ),
            (usb_host_gamepad.Button.DOWN,           .2,  .5 ),
            (usb_host_gamepad.Button.START,          .6,  .4 ),
            (usb_host_gamepad.Button.SELECT,         .4,  .4 ),
            (usb_host_gamepad.Button.HOME,           .5,  .4 ),
            (usb_host_gamepad.Button.L1,             .1,  .1 ),
            (usb_host_gamepad.Button.L2,             .2,  .1 ),
            (usb_host_gamepad.Button.L3,             .3,  .1 ),
            (usb_host_gamepad.Button.R1,             .9,  .1 ),
            (usb_host_gamepad.Button.R2,             .8,  .1 ),
            (usb_host_gamepad.Button.R3,             .7,  .1 ),
            (usb_host_gamepad.Button.JOYSTICK_LEFT,  .25, .75),
            (usb_host_gamepad.Button.JOYSTICK_RIGHT, .45, .75),
            (usb_host_gamepad.Button.JOYSTICK_UP,    .35, .6 ),
            (usb_host_gamepad.Button.JOYSTICK_DOWN,  .35, .9 ),
        )
        self._circles = []
        for button, x, y in self._buttons:
            circle = vectorio.Circle(
                pixel_shader=self._released_palette,
                radius=button_size//2,
                x=int(x*self.width),
                y=int(y*self.height),
            )
            self._circles.append(circle)
            self.append(circle)

        self._joystick_outer_size = int(size * .15)
        self._joystick_inner_size = int(size * .05)

        joystick_outer_palette = displayio.Palette(1)
        joystick_outer_palette[0] = 0x000000

        joystick_inner_palette = displayio.Palette(1)
        joystick_inner_palette[0] = 0xffffff

        self._joysticks = (
            ("left_joystick", .35, .75),
            ("right_joystick", .65, .75),
        )
        self._joystick_circles = []
        for name, x, y in self._joysticks:
            outer = vectorio.Circle(
                pixel_shader=joystick_outer_palette,
                radius=self._joystick_outer_size//2,
                x=int(x*self.width),
                y=int(y*self.height),
            )
            self.append(outer)
            inner = vectorio.Circle(
                pixel_shader=joystick_inner_palette,
                radius=self._joystick_inner_size//2,
                x=int(x*self.width),
                y=int(y*self.height),
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
            for i, data in enumerate(self._buttons):
                button = self._gamepad.buttons[data[0]]
                if button.changed:
                    self._circles[i].pixel_shader = self._pressed_palette if button.pressed else self._released_palette
            for i, data in enumerate(self._joysticks):
                name, x, y = data
                js_x, js_y = getattr(self._gamepad, name)
                self._joystick_circles[i].x = int((js_x * self._joystick_outer_size // 2) + (x * self.width))
                self._joystick_circles[i].y = int((-js_y * self._joystick_outer_size // 2) + (y * self.height))
            return self._gamepad.buttons.is_changed()
        return False

gamepads = [Gamepad(i+1) for i in range(2)]

gap = (display.width - sum((x.width for x in gamepads))) // (len(gamepads) + 1)
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
    
    time.sleep(1/30)
