# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: MIT
import pygame

import relic_usb_host_gamepad
from relic_usb_host_gamepad import (
    BUTTON_A,
    BUTTON_B,
    BUTTON_DOWN,
    BUTTON_HOME,
    BUTTON_JOYSTICK_DOWN,
    BUTTON_JOYSTICK_LEFT,
    BUTTON_JOYSTICK_RIGHT,
    BUTTON_JOYSTICK_UP,
    BUTTON_L1,
    BUTTON_L2,
    BUTTON_L3,
    BUTTON_LEFT,
    BUTTON_R1,
    BUTTON_R2,
    BUTTON_R3,
    BUTTON_RIGHT,
    BUTTON_SELECT,
    BUTTON_START,
    BUTTON_TOUCH_PAD,
    BUTTON_UP,
    BUTTON_X,
    BUTTON_Y,
)

SUPPORTED_EVENT_TYPES = (
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
    pygame.JOYAXISMOTION,
    pygame.JOYHATMOTION,
)
"""All the event types supported within :meth:`Gamepad.process_event`.
"""

# list of supported devices
SUPPORTED_DEVICE_NAMES = (
    "Nintendo Switch Pro Controller",
    "Xbox 360 Controller",
    "USB gamepad",  # Adafruit SNES controller
    "PS4 Controller",
    "Sony Interactive Entertainment Wireless Controller",  # PS5 controller
)
"""All the devices supported by :class:`Gamepad` as identified by their name.
"""


def is_joystick_supported(joystick: pygame.joystick.Joystick | str) -> bool:
    """Determine whether or not a joystick object is compatible with :class:`Gamepad`."""
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
    """Helper class which is used to transpose events from pygame joysticks to be compatible with
    the :class:`relic_usb_host_gamepad.Gamepad` API.
    """

    def __init__(self, id: int = 0, debug: bool = False):
        """Initializes the :class:`Gamepad` device helper.

        :param id: The device index used by pygame. Must be less than
            :func:`pygame.joystick.get_count`.
        :type id: int
        :param debug: Set this value to `True` to generate verbose debug messages over REPL.
        :type debug: bool
        """
        super().__init__(debug=debug)

        # initialize pygame joysticks module
        if not pygame.joystick.get_init():
            pygame.joystick.init()

        if id >= pygame.joystick.get_count():
            raise ValueError("Invalid joystick id requested")

        self._joystick = pygame.joystick(id)
        self._name = self._joystick.get_name()

        if not is_joystick_supported(self._name):
            raise NotImplementedError(f'Joystick of type "{self._name:s}" not supported')

        self._axes = [0] * self._joystick.get_numaxes()
        self._hats = [0] * self._joystick.get_numhats()

    def update(self) -> bool:
        """Update the gamepad device.

        :return: Whether or not the state of the gamepad was updated.
        :rtype: bool
        """
        self.update_axes()
        return self.process_events(pygame.event.get())

    def disconnect(self) -> bool:
        """Calls :meth:`pygame.joystick.Joystick.quit`.

        :return: Always returns `True`.
        :rtype: bool
        """
        self._joystick.quit()
        return True

    def process_events(self, events: list) -> bool:
        """Read a list of pygame events and update the corresponding gamepad state. The method is
        typically called by :meth:`Gamepad.update`.

        :param events: A list of :class:`pygame.event.Event` objects typically obtained via
            :func:`pygame.event.get`.
        :type events: list
        :return: Whether or not the state of any buttons was changed.
        :rtype: bool
        """
        # reset button changes
        self._state.buttons._changed = 0

        changed = False
        for event in events:
            if self.process_event(event):
                changed = True
        return changed

    def process_event(self, event: pygame.event.Event) -> bool:
        """Read a :class:`pygame.event.Event` object and update the state of the gamepad buttons.

        :param event: A :class:`pygame.event.Event` object typically obtained via
            :func:`pygame.event.get`.
        :type event: pygame.event.Event
        :return: Whether or not the state of a button was changed.
        :rtype: bool
        """
        if event.type not in SUPPORTED_EVENT_TYPES:
            return False

        if event.instance_id != self._joystick.get_instance_id():
            return False

        changed = False

        if (
            event.type in set(pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP)
            and self._name in _JOYSTICK_BUTTONS
            and event.button < len(_JOYSTICK_BUTTONS[self._name])
        ):
            self._state[_JOYSTICK_BUTTONS[self._name][event.button]] = (
                event.type == pygame.JOYBUTTONDOWN
            )
            changed = True

        elif (
            event.type == pygame.JOYAXISMOTION
            and self._name in _JOYSTICK_AXES
            and event.axis < len(_JOYSTICK_AXES[self._name])
        ):
            axis = _JOYSTICK_AXES[self._name][event.axis]
            if (
                isinstance(axis, int)
                and (value := int(event.value >= self.trigger_threshold)) != self._axes[event.axis]
            ):
                self._state[axis] = value
                self._axes[event.axis] = value
                changed = True
            elif (
                isinstance(axis, tuple)
                and (
                    value := (
                        1
                        if event.value >= self.joystick_threshold
                        else (-1 if event.value <= -self.joystick_threshold else 0)
                    )
                )
                != self._axes[event.axis]
            ):
                if self._axes[event.axis] != 0:
                    self._state[axis[int(self._axes[event.axis] > 0)]] = False
                    changed = True
                if value != 0:
                    self._state[axis[int(value > 0)]] = True
                    changed = True
                self._axes[event.axis] = value

        elif (
            event.type == pygame.JOYHATMOTION
            and self._name in _JOYSTICK_HATS
            and event.hat < len(_JOYSTICK_HATS[self._name])
            and _JOYSTICK_HATS[self._name][event.hat] is not None
        ):
            if self._hats[event.hat] != 0:
                self._state[
                    _JOYSTICK_HATS[self._name][event.hat][int(self._hats[event.hat] > 0)]
                ] = False
                changed = True
            if event.value != 0:
                self._state[_JOYSTICK_HATS[self._name][event.hat][int(event.value > 0)]] = True
                changed = True
            self._hats[event.hat] = event.value

        return changed

    def update_axes(self) -> bool:
        """Updates the values of :prop:`Gamepad.left_joystick` and :prop:`Gamepad.right_joystick` if
        they are supported by the device.

        :return: Whether or not the gamepad's joysticks were updated.
        :rtype: bool
        """
        if self._name not in _JOYSTICK_AXES:
            return False

        for i, axis in enumerate(_JOYSTICK_AXES[self._name]):
            if isinstance(axis, tuple):
                if axis[0] in set(BUTTON_JOYSTICK_LEFT, BUTTON_JOYSTICK_RIGHT):
                    self._state._left_joystick_x = self._apply_deadzone(
                        self._joystick.get_axis(i), axis[0] == BUTTON_JOYSTICK_RIGHT
                    )[0]

                elif axis[0] == BUTTON_JOYSTICK_DOWN:
                    self._state._left_joystick_y = self._apply_deadzone(
                        self._joystick.get_axis(i), axis[0] == BUTTON_JOYSTICK_DOWN
                    )[0]

        return True
