# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: MIT
import pygame
import relic_usb_host_gamepad
from relic_usb_host_gamepad import (
    BUTTON_A,
    BUTTON_B,
    BUTTON_X,
    BUTTON_Y,
    BUTTON_SELECT,
    BUTTON_HOME,
    BUTTON_START,
    BUTTON_L3,
    BUTTON_R3,
    BUTTON_L1,
    BUTTON_R1,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_TOUCH_PAD,
    BUTTON_JOYSTICK_LEFT,
    BUTTON_JOYSTICK_RIGHT,
    BUTTON_JOYSTICK_UP,
    BUTTON_JOYSTICK_DOWN,
    BUTTON_L2,
    BUTTON_R2,
)

SUPPORTED_EVENT_TYPES = (
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
    pygame.JOYAXISMOTION,
    pygame.JOYHATMOTION,
)

# list of supported devices
SUPPORTED_DEVICE_NAMES = (
    "Nintendo Switch Pro Controller",
    "Xbox 360 Controller",
    "USB gamepad",  # Adafruit SNES controller
    "PS4 Controller",
    "Sony Interactive Entertainment Wireless Controller",  # PS5 controller
)

def is_joystick_supported(joystick: pygame.joystick.Joystick|str) -> bool:
    name = joystick.get_name() if isinstance(joystick, pygame.joystick.Joystick) else joystick
    return name in SUPPORTED_DEVICE_NAMES

# pygame => relic_usb_host_gamepad mapping
_JOYSTICK_BUTTONS = {
    "Nintendo Switch Pro Controller": (
        BUTTON_A,
        BUTTON_B,
        BUTTON_X,
        BUTTON_Y,
        BUTTON_SELECT,
        BUTTON_HOME,
        BUTTON_START,
        BUTTON_L3,
        BUTTON_R3,
        BUTTON_L1,
        BUTTON_R1,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_RIGHT,
        None,  # capture
    ),
    "Xbox 360 Controller": (
        BUTTON_A,
        BUTTON_B,
        BUTTON_X,
        BUTTON_Y,
        BUTTON_L1,
        BUTTON_R1,
        BUTTON_SELECT,
        BUTTON_START,
        BUTTON_L3,
        BUTTON_R3,
        BUTTON_HOME,
    ),
    "USB gamepad": (  # Adafruit SNES controller
        BUTTON_X,
        BUTTON_A,
        BUTTON_B,
        BUTTON_Y,
        BUTTON_L1,
        BUTTON_R1,
        None,  # unknown
        None,  # unknown
        BUTTON_SELECT,
        BUTTON_START,
    ),
    "PS4 Controller": (
        BUTTON_A,
        BUTTON_B,
        BUTTON_Y,
        BUTTON_X,
        BUTTON_SELECT,
        BUTTON_HOME,
        BUTTON_START,
        BUTTON_L3,
        BUTTON_R3,
        BUTTON_L1,
        BUTTON_R1,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_RIGHT,
        BUTTON_TOUCH_PAD,
    ),
    "Sony Interactive Entertainment Wireless Controller": (
        BUTTON_A,
        BUTTON_B,
        BUTTON_Y,
        BUTTON_X,
        BUTTON_L1,
        BUTTON_R1,
        None,  # left trigger
        None,  # right trigger
        BUTTON_SELECT,
        BUTTON_START,
        BUTTON_HOME,
        BUTTON_L3,
        BUTTON_R3,
    ),
}

_JOYSTICK_HATS = {
    "Xbox 360 Controller": (
        (BUTTON_LEFT, BUTTON_RIGHT),
        (BUTTON_DOWN, BUTTON_UP),
    ),
    "Sony Interactive Entertainment Wireless Controller": (
        (BUTTON_LEFT, BUTTON_RIGHT),
        (BUTTON_DOWN, BUTTON_UP),
    ),
}

_JOYSTICK_AXES = {
    "Xbox 360 Controller": (
        (BUTTON_JOYSTICK_LEFT, BUTTON_JOYSTICK_RIGHT),
        (BUTTON_JOYSTICK_UP, BUTTON_JOYSTICK_DOWN),
        BUTTON_L2,
        None,  # right stick left/right
        None,  # right stick up/down
        BUTTON_R2,
    ),
    "USB gamepad": (  # Adafruit SNES controller
        (BUTTON_LEFT, BUTTON_RIGHT),
        (BUTTON_UP, BUTTON_DOWN),
    ),
    "PS4 Controller": (
        (BUTTON_JOYSTICK_LEFT, BUTTON_JOYSTICK_RIGHT),
        (BUTTON_JOYSTICK_UP, BUTTON_JOYSTICK_DOWN),
        None,  # right stick left/right
        None,  # right stick up/down
        BUTTON_L2,
        BUTTON_R2,
    ),
    "Sony Interactive Entertainment Wireless Controller": (
        (BUTTON_JOYSTICK_LEFT, BUTTON_JOYSTICK_RIGHT),
        (BUTTON_JOYSTICK_UP, BUTTON_JOYSTICK_DOWN),
        BUTTON_L2,
        None,  # right stick left/right
        None,  # right stick up/down
        BUTTON_R2,
    ),
}

class Gamepad(relic_usb_host_gamepad.Gamepad):

    def __init__(self, id: int = 0, debug: bool = False):
        super().__init__(debug=debug)

        # initialize pygame joysticks module
        if not pygame.joystick.get_init():
            pygame.joystick.init()

        if id >= pygame.joystick.get_count():
            raise ValueError("Invalid joystick id requested")
        
        self._joystick = pygame.joystick(id)
        self._name = self._joystick.get_name()

        if not is_joystick_supported(self._name):
            raise NotImplementedError("Joystick of type \"{:s}\" not supported".format(self._name))
        
        self._axes = [0] * self._joystick.get_numaxes()
        self._hats = [0] * self._joystick.get_numhats()

    def update(self) -> bool:
        self.update_axes()

        changed = False
        for event in pygame.event.get():
            if self.process_event(event):
                changed = True
        return changed

    def disconnect(self) -> bool:
        self._joystick.quit()
        return True
    
    def process_event(self, event: pygame.event.Event) -> bool:
        changed = False

        if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP) and self._name in _JOYSTICK_BUTTONS and event.button < len(_JOYSTICK_BUTTONS[self._name]):
            self._state[_JOYSTICK_BUTTONS[self._name][event.button]] = event.type == pygame.JOYBUTTONDOWN
            changed = True

        elif event.type == pygame.JOYAXISMOTION and self._name in _JOYSTICK_AXES and event.axis < len(_JOYSTICK_AXES[self._name]):
            axis = _JOYSTICK_AXES[self._name][event.axis]
            if isinstance(axis, int):
                value = int(event.value >= self.trigger_threshold)
                if value != self._axes[event.axis]:
                    self._state[axis] = value
                    changed = True
                self._axes[event.axis] = value
            else:
                value = 1 if event.value >= self.joystick_threshold else (-1 if event.value <= -self.joystick_threshold else 0)
                if value != self._axes[event.axis]:
                    if self._axes[event.axis] != 0:
                        self._state[axis[int(self._axes[event.axis] > 0)]] = False
                        changed = True
                    if value != 0:
                        self._state[axis[int(value > 0)]] = True
                        changed = True
                    self._axes[event.axis] = value

        elif event.type == pygame.JOYHATMOTION and self._name in _JOYSTICK_HATS and event.hat < len(_JOYSTICK_HATS[self._name]) and _JOYSTICK_HATS[self._name][event.hat] is not None:
            if self._hats[event.hat] != 0:
                self._state[_JOYSTICK_HATS[self._name][event.hat][int(self._hats[event.hat] > 0)]] = False
                changed = True
            if event.value != 0:
                self._state[_JOYSTICK_HATS[self._name][event.hat][int(event.value > 0)]] = True
                changed = True
            self._hats[event.hat] = event.value
        
        return changed
    
    def update_axes(self) -> bool:
        if self._name not in _JOYSTICK_AXES:
            return False
        
        for i, axis in enumerate(_JOYSTICK_AXES[self._name]):
            if isinstance(axis, tuple):
                if axis[0] in (BUTTON_JOYSTICK_LEFT, BUTTON_JOYSTICK_RIGHT):
                    self._state._left_joystick_x = self._apply_deadzone(self._joystick.get_axis(i), axis[0] == BUTTON_JOYSTICK_RIGHT)[0]

                elif axis[0] == BUTTON_JOYSTICK_DOWN:
                    self._state._left_joystick_y = self._apply_deadzone(self._joystick.get_axis(i), axis[0] == BUTTON_JOYSTICK_DOWN)[0]

        return True
