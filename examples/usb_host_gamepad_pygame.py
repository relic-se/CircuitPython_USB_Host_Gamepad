# SPDX-FileCopyrightText: 2025 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3
from blinka_displayio_pygamedisplay import PyGameDisplay
from relic_usb_host_gamepad import BUTTON_NAMES
from relic_usb_host_gamepad.pygame import Gamepad, EVENT_TYPES

display = PyGameDisplay(
    width=640, height=480,
    caption="PyGame Gamepad Test",
)

gamepad = Gamepad()

def update() -> None:
    for event in gamepad.events:
        print(
            "{:s} {:s}".format(
                BUTTON_NAMES[event.key_number],
                ("Pressed" if event.pressed else "Released"),
            )
        )
    gamepad.reset_button_changes()

display.event_loop(
    on_time=update,
    on_event=gamepad.process_event,
    events=EVENT_TYPES,
)
