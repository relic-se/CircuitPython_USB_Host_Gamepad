# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
# SPDX-FileCopyrightText: Copyright (c) 2025 Sam Blenny
#
# SPDX-License-Identifier: MIT
"""
`relic_usb_host_gamepad`
================================================================================

CircuitPython USB host driver for game controller devices.

* Author(s): Cooper Dalrymple

Implementation Notes
--------------------

**Hardware:**

* `Adafruit Fruit Jam <https://www.adafruit.com/product/6200>`_
* `Adafruit Feather RP2040 with USB Type A Host <https://www.adafruit.com/product/5723>`_
* `Adafruit SNES Controller <https://www.adafruit.com/product/6285>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads
* Adafruit's USB Host Descriptors library:
  https://github.com/adafruit/Adafruit_CircuitPython_USB_Host_Descriptors
"""

# imports

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/relic-se/CircuitPython_USB_Host_Gamepad.git"

import struct
import time

import keypad
import usb.core
from micropython import const
from relic_usb_host_descriptor_parser import DeviceDescriptor
from usb.util import SPEED_HIGH

_MAX_TIMEOUTS = const(99)
_SEARCH_DELAY = const(1)
_TRIGGER_THRESHOLD = const(128)
_JOYSTICK_THRESHOLD = const(8192)

# USB detected device types

DEVICE_TYPE_UNKNOWN = const(0)
"""An unknown usb device."""

DEVICE_TYPE_SWITCH_PRO = const(1)  # 057e:2009 clones of Switch Pro Controller
"""The type of a usb gamepad device which has been identified as a Switch Pro Controller."""

DEVICE_TYPE_ADAFRUIT_SNES = const(2)  # 081f:e401 generic SNES layout HID, low-speed
"""The type of a usb gamepad device which has been identified as an Adafruit SNES controller."""

DEVICE_TYPE_8BITDO_ZERO2 = const(3)  # 2dc8:9018 mini SNES layout, HID over USB-C
"""The type of a usb gamepad device which has been identified as an 8BitDo Zero 2 controller."""

DEVICE_TYPE_XINPUT = const(4)  # (vid:pid vary) Clones of Xbox360 controller
"""The type of a usb gamepad device which has been identified as an X-Input compatible controller.
"""

DEVICE_TYPE_POWERA_WIRED = const(5)  # 20d6:a711 PowerA Wired Controller (for Switch)
"""The type of a usb gamepad device which has been identified as a PowerA Wired Controller."""

_DEVICE_TYPES = (
    # (index, vid, pid),
    (DEVICE_TYPE_SWITCH_PRO, 0x057E, 0x2009),
    (DEVICE_TYPE_ADAFRUIT_SNES, 0x081F, 0xE401),
    (DEVICE_TYPE_8BITDO_ZERO2, 0x2DC8, 0x9018),
    (DEVICE_TYPE_POWERA_WIRED, 0x20D6, 0xA711),
)

_DEVICE_CLASSES = (
    # (index, device class, device subclass, interface 0 class, interface 0 subclass),
    (DEVICE_TYPE_XINPUT, 0xFF, 0xFF, 0xFF, 0x5D),
)

DEVICE_NAMES = (
    "Unknown",
    "Switch Pro Controller",
    "Adafruit SNES Controller",
    "8BitDo Zero 2",
    "Generic XInput",
    "PowerA Wired Controller",
)
"""A list of all device names following the appropriate device type id. Useful for print statements.
"""

BUTTON_NAMES = (
    "A",
    "B",
    "X",
    "Y",
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
    "START",
    "SELECT",
    "HOME",
    "L1",
    "R1",
    "L2",
    "R2",
    "L3",
    "R3",
    "JOYSTICK_UP",
    "JOYSTICK_DOWN",
    "JOYSTICK_LEFT",
    "JOYSTICK_RIGHT",
)
"""A list of all button names following the appropriate key number order. Useful for print
statements.
"""

BUTTON_A = 0
"""The ID of the "A" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_B = 1
"""The ID of the "B" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_X = 2
"""The ID of the "X" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_Y = 3
"""The ID of the "Y" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_UP = 4
"""The ID of the "D-Pad Up" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_DOWN = 5
"""The ID of the "D-Pad Down" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_LEFT = 6
"""The ID of the "D-Pad Left" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_RIGHT = 7
"""The ID of the "D-Pad Right" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_START = 8
"""The ID of the "Start" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_SELECT = 9
"""The ID of the "Select" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_HOME = 10
"""The ID of the "Home" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_L1 = 11
"""The ID of the "L1" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_R1 = 12
"""The ID of the "R1" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_L2 = 13
"""The ID of the "L2" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_R2 = 14
"""The ID of the "R2" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_L3 = 15
"""The ID of the "L3" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_R3 = 16
"""The ID of the "R3" button. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_JOYSTICK_UP = 17
"""The ID of the "Joystick Up" button which is triggered when the left joystick exceeds the analog
threshold in the up direction. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_JOYSTICK_DOWN = 18
"""The ID of the "Joystick Down" button which is triggered when the left joystick exceeds the analog
threshold in the down direction. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_JOYSTICK_LEFT = 19
"""The ID of the "Joystick Left" button which is triggered when the left joystick exceeds the analog
threshold in the left direction. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""

BUTTON_JOYSTICK_RIGHT = 20
"""The ID of the "Joystick Right" button which is triggered when the left joystick exceeds the
analog threshold in the right direction. Used as the :attr:`keypad.Event.key_number` attribute in
:attr:`Gamepad.events`.
"""


class Button:
    def __init__(self, index: int):
        self._mask = 1 << index

    def __get__(self, obj, objtype=None):
        return obj._pressed & self._mask

    def __set__(self, obj, value: bool):
        if bool(obj._pressed & self._mask) != value:
            obj._changed |= self._mask
        else:
            obj._changed &= ~self._mask

        if value:
            obj._pressed |= self._mask
        else:
            obj._pressed &= ~self._mask


class Buttons:
    """The class which handles the state of each digital button of a :class:`Gamepad` device."""

    A: bool = Button(BUTTON_A)
    """Whether or not the "A" button is pressed."""

    B: bool = Button(BUTTON_B)
    """Whether or not the "B" button is pressed."""

    X: bool = Button(BUTTON_X)
    """Whether or not the "X" button is pressed."""

    Y: bool = Button(BUTTON_Y)
    """Whether or not the "Y" button is pressed."""

    UP: bool = Button(BUTTON_UP)
    """Whether or not the "Up" button is pressed."""

    DOWN: bool = Button(BUTTON_DOWN)
    """Whether or not the "Down" button is pressed."""

    LEFT: bool = Button(BUTTON_LEFT)
    """Whether or not the "Left" button is pressed."""

    RIGHT: bool = Button(BUTTON_RIGHT)
    """Whether or not the "Right" button is pressed."""

    START: bool = Button(BUTTON_START)
    """Whether or not the "Start" button is pressed."""

    SELECT: bool = Button(BUTTON_SELECT)
    """Whether or not the "Select" button is pressed."""

    HOME: bool = Button(BUTTON_HOME)
    """Whether or not the "Home" button is pressed."""

    L1: bool = Button(BUTTON_L1)
    """Whether or not the "L1" button is pressed."""

    R1: bool = Button(BUTTON_R1)
    """Whether or not the "R1" button is pressed."""

    L2: bool = Button(BUTTON_L2)
    """Whether or not the "L2" button is pressed."""

    R2: bool = Button(BUTTON_R2)
    """Whether or not the "R2" button is pressed."""

    L3: bool = Button(BUTTON_L3)
    """Whether or not the "L3" button is pressed."""

    R3: bool = Button(BUTTON_R3)
    """Whether or not the "R3" button is pressed."""

    JOYSTICK_UP: bool = Button(BUTTON_JOYSTICK_UP)
    """Whether or not the "Joystick Up" button is pressed which occurs when the left joystick
    exceeds the analog threshold in the up direction.
    """

    JOYSTICK_DOWN: bool = Button(BUTTON_JOYSTICK_DOWN)
    """Whether or not the "Joystick Down" button is pressed which occurs when the left joystick
    exceeds the analog threshold in the down direction.
    """

    JOYSTICK_LEFT: bool = Button(BUTTON_JOYSTICK_LEFT)
    """Whether or not the "Joystick Left" button is pressed which occurs when the left joystick
    exceeds the analog threshold in the left direction.
    """

    JOYSTICK_RIGHT: bool = Button(BUTTON_JOYSTICK_RIGHT)
    """Whether or not the "Joystick Right" button is pressed which occurs when the left joystick
    exceeds the analog threshold in the right direction.
    """

    def __init__(self):
        """Initializes the state of all digital button inputs."""
        self.reset()

    def __iter__(self):
        for x in BUTTON_NAMES:
            yield getattr(self, x)

    def __getitem__(self, index: int) -> bool:
        return getattr(self, BUTTON_NAMES[index])

    def __len__(self) -> int:
        return len(BUTTON_NAMES)

    @property
    def events(self) -> tuple:
        """A list of all changed button states since the last :class:`Gamepad` device update
        represented as :class:`keypad.Event` objects. The :attr:`keypad.Event.key_number` value
        represents the button ID.
        """
        return tuple([keypad.Event(i, x) for i, x in enumerate(self) if self._changed & (1 << i)])

    @property
    def changed(self) -> bool:
        """Whether or not the state of any buttons has changed since the last :class:`Gamepad`
        device update.
        """
        try:
            next(x for i, x in enumerate(self) if self._changed & (1 << i))
        except StopIteration:
            return False
        finally:
            return True

    def reset(self) -> None:
        """Reset the state of all buttons to be released."""
        self._pressed = 0
        self._changed = 0


class State:
    def __init__(self):
        self._buttons = Buttons()
        self.reset()

    @property
    def buttons(self) -> Buttons:
        return self._buttons

    @property
    def left_trigger(self) -> float:
        return self._left_trigger / 255

    @left_trigger.setter
    def left_trigger(self, value: int | float) -> None:
        if type(value) is float:
            value = int(value * 255)
        self._left_trigger = min(max(value, 0), 255)
        self._buttons.L2 = self._left_trigger >= _TRIGGER_THRESHOLD

    @property
    def right_trigger(self) -> float:
        return self._right_trigger / 255

    @right_trigger.setter
    def right_trigger(self, value: int | float) -> None:
        if type(value) is float:
            value = int(value * 255)
        self._right_trigger = min(max(value, 0), 255)
        self._buttons.R2 = self._right_trigger >= _TRIGGER_THRESHOLD

    @property
    def left_joystick(self) -> tuple[int]:
        return (self._left_joystick_x / 32768, self._left_joystick_y / 32768)

    @left_joystick.setter
    def left_joystick(self, value: tuple[int]) -> None:
        if len(value) != 2:
            raise ValueError("value must be in the format of (x, y)")

        x, y = value
        if type(x) is float:
            x = int(x * 32767)
        if type(y) is float:
            y = int(y * 32767)
        self._left_joystick_x = min(max(x, -32768), 32767)
        self._left_joystick_y = min(max(y, -32768), 32767)

        self._buttons.JOYSTICK_RIGHT = self._left_joystick_x >= _JOYSTICK_THRESHOLD
        self._buttons.JOYSTICK_LEFT = self._left_joystick_x <= -_JOYSTICK_THRESHOLD
        self._buttons.JOYSTICK_UP = self._left_joystick_y >= _JOYSTICK_THRESHOLD
        self._buttons.JOYSTICK_DOWN = self._left_joystick_y <= -_JOYSTICK_THRESHOLD

    @property
    def right_joystick(self) -> tuple:
        return (self._right_joystick_x / 32768, self._right_joystick_y / 32768)

    @right_joystick.setter
    def right_joystick(self, value: tuple) -> None:
        if len(value) != 2:
            raise ValueError("value must be in the format of (x, y)")

        x, y = value
        if type(x) is float:
            x = int(x * 32767)
        if type(y) is float:
            y = int(y * 32767)

        self._right_joystick_x = min(max(x, -32768), 32767)
        self._right_joystick_y = min(max(y, -32768), 32767)

    def reset(self) -> None:
        self._buttons.reset()
        self._left_trigger = 0
        self._right_trigger = 0
        self._left_joystick_x = 0
        self._left_joystick_y = 0
        self._right_joystick_x = 0
        self._right_joystick_y = 0


def _get_device_type(
    device: usb.core.Device, device_descriptor: DeviceDescriptor = None, debug: bool = False
) -> int:
    # identify device by id
    device_id = (device.idVendor, device.idProduct)
    if debug:
        print("identifying device by id (vid+pid):", [hex(x) for x in device_id])
    for device_type, type_vid, type_pid in _DEVICE_TYPES:
        if device_id == (type_vid, type_pid):
            if debug:
                print("found device type:", device_type)
            return device_type

    # identify device by class
    if device_descriptor is None:
        device_descriptor = DeviceDescriptor(device)
    class_identifier = device_descriptor.get_class_identifier()
    if debug:
        print("identifying device by class identifier:", [hex(x) for x in class_identifier])
    for (
        device_type,
        type_class,
        type_subclass,
        type_int_class,
        type_int_subclass,
    ) in _DEVICE_CLASSES:
        if class_identifier == (type_class, type_subclass, type_int_class, type_int_subclass):
            if debug:
                print("found device type:", device_type)
            return device_type

    return DEVICE_TYPE_UNKNOWN


def _report_equals(a: bytearray, b: bytearray, length: int = None) -> bool:
    if a is None and b is not None or b is None and a is not None:
        return False

    if length is None:
        length = min(len(a), len(b))
    for i in range(length):
        if a[i] != b[i]:
            return False
    return True


class Device:
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        device: usb.core.Device,
        device_type: int,
        device_descriptor: DeviceDescriptor = None,
        configuration: int = 0,
        interface: int = 0,
        debug: bool = False,
    ):
        if interface != 0:
            raise ValueError("Only interface 0 is supported")

        self._device = device
        self._device_type = device_type
        self._led = 0
        self._debug = debug

        self._descriptor = (
            DeviceDescriptor(device) if device_descriptor is None else device_descriptor
        )
        self._configuration = self._descriptor.configurations[configuration]
        self._interface = self._configuration.interfaces[interface]
        self._in_endpoint = self._interface.in_endpoint
        self._out_endpoint = self._interface.out_endpoint
        if self._in_endpoint is None or self._out_endpoint is None:
            raise ValueError("invalid interface endpoints")

        # make sure CircuitPython core is not claiming the device
        if device.is_kernel_driver_active(interface):
            if debug:
                print("detaching device from kernel")
            device.detach_kernel_driver(interface)

        # set configuration
        if self._debug:
            print("set configuration:", self._configuration.value)
        device.set_configuration(self._configuration.value)

        self._max_packet_size = min(
            64, max(self._in_endpoint.max_packet_size, self._out_endpoint.max_packet_size)
        )
        self._report = bytearray(self._max_packet_size)
        self._previous_report = bytearray(self._max_packet_size)

        # Low-speed & Full-speed: max time between polling requests = interval * 1 ms
        # High-speed: max time between polling requests = math.pow(2, bInterval-1) * 125 µs
        self._interval = max(self._in_endpoint.interval, self._out_endpoint.interval)
        if device.speed == SPEED_HIGH:
            self._interval = (2 << (self._interval - 1)) >> 3
        self._timestamp = time.monotonic()

    @property
    def device_id(self) -> tuple:
        return (self._device.idVendor, self._device.idProduct)

    @property
    def device_type(self) -> int:
        return self._device_type

    @property
    def led(self) -> int:
        return self._led

    @led.setter
    def led(self, value: int) -> None:
        if value is None:
            value = 0
        self._led = value

    def read_state(self, state: State) -> bool:
        if (current_time := time.monotonic()) - self._timestamp < self._interval / 1000:
            return False
        self._timestamp = current_time

        packet_size = self.read()
        if not packet_size or _report_equals(self._report, self._previous_report, packet_size):
            return False
        self._previous_report = self._report[:]

        if self._debug:
            print("report:", self._report[:packet_size])

        self._update_state(state)
        return True

    def _update_state(self) -> None:
        pass

    def write(self, data: bytearray, acknowledge: bool = True) -> bool:
        try:
            self._device.write(self._out_endpoint.address, data, timeout=self._interval)
            if not acknowledge:
                return True
        except usb.core.USBTimeoutError:
            return False

        # wait for ACK
        for i in range(8):
            try:
                self.read()
                return True
            except (usb.core.USBTimeoutError, usb.core.USBError):
                pass
        return False

    def read(self) -> int:
        return self._device.read(self._in_endpoint.address, self._report, timeout=self._interval)

    def flush(self) -> None:
        for i in range(8):
            try:
                self.read()
            except usb.core.USBTimeoutError:
                pass


class SwitchProDevice(Device):
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, DEVICE_TYPE_SWITCH_PRO, device_descriptor=device_descriptor, debug=debug
        )

        # perform handshake
        for msg in (
            b"\x80\x01",  # get device type and mac address
            b"\x80\x02",  # handshake
            b"\x80\x03",  # set faster baud rate
            b"\x80\x02",  # handshake
            b"\x80\x04",  # use USB HID only and disable timeout
            # set input report mode to standard
            b"\x01\x06\x00\x00\x00\x00\x00\x00\x00\x00\x03\x30",
            # set home LED
            b"\x01\x0b\x00\x00\x00\x00\x00\x00\x00\x00\x38\x01\x00\x00\x11\x11",
        ):
            if not self.write(msg):
                raise ValueError("SwitchPro HANDSHAKE GLITCH")

    @property
    def led(self) -> int:
        return self._led

    @led.setter
    def led(self, value: int) -> None:
        if value is None:
            value = 0
        self._led = min(max(value, 0), 4)
        msg = bytearray(b"\x01\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x30\x00")
        for i in range(4):
            if self._led > i:
                msg[len(msg) - 1] |= 1 << i
        self.write(msg)

    def _update_state(self, state: State) -> None:
        state.buttons.Y = bool(self._report[2] & 0x01)
        state.buttons.X = bool(self._report[2] & 0x02)
        state.buttons.B = bool(self._report[2] & 0x04)
        state.buttons.A = bool(self._report[2] & 0x08)
        state.buttons.R1 = bool(self._report[2] & 0x40)
        state.buttons.SELECT = bool(self._report[3] & 0x01)
        state.buttons.START = bool(self._report[3] & 0x02)
        state.buttons.DOWN = bool(self._report[4] & 0x01)
        state.buttons.UP = bool(self._report[4] & 0x02)
        state.buttons.RIGHT = bool(self._report[4] & 0x04)
        state.buttons.LEFT = bool(self._report[4] & 0x08)
        state.buttons.L1 = bool(self._report[4] & 0x40)


class XInputDevice(Device):
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, DEVICE_TYPE_XINPUT, device_descriptor=device_descriptor, debug=debug
        )
        self.flush()  # ignore initial reports before normal operation

    @property
    def led(self) -> int:
        return self._led

    @led.setter
    def led(self, value: int) -> None:
        if value is None:
            value = 0
        self._led = min(max(value, 0), 2)
        msg = bytearray(b"\x01\x03\x02")
        for i in range(2):
            if self._led > i:
                msg[len(msg) - 1] |= 1 << (1 - i)
        self.write(msg)

    def _update_state(self, state: State) -> None:
        state.buttons.UP = bool(self._report[2] & 0x01)
        state.buttons.DOWN = bool(self._report[2] & 0x02)
        state.buttons.LEFT = bool(self._report[2] & 0x04)
        state.buttons.RIGHT = bool(self._report[2] & 0x08)
        state.buttons.START = bool(self._report[2] & 0x10)
        state.buttons.SELECT = bool(self._report[2] & 0x20)
        state.buttons.L1 = bool(self._report[3] & 0x01)
        state.buttons.R1 = bool(self._report[3] & 0x02)
        state.buttons.HOME = bool(self._report[3] & 0x04)
        state.buttons.B = bool(self._report[3] & 0x10)
        state.buttons.A = bool(self._report[3] & 0x20)
        state.buttons.Y = bool(self._report[3] & 0x40)
        state.buttons.X = bool(self._report[3] & 0x80)

        state.left_trigger = self._report[4]
        state.right_trigger = self._report[5]

        state.left_joystick = (
            struct.unpack("h", self._report[6:8])[0],  # x
            struct.unpack("h", self._report[8:10])[0],  # y
        )
        state.right_joystick = (
            struct.unpack("h", self._report[10:12])[0],  # x
            struct.unpack("h", self._report[12:14])[0],  # y
        )


class AdafruitSnesDevice(Device):
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, DEVICE_TYPE_ADAFRUIT_SNES, device_descriptor=device_descriptor, debug=debug
        )

    def _update_state(self, state: State) -> None:
        state.buttons.LEFT = self._report[0] == 0x00
        state.buttons.RIGHT = self._report[0] == 0xFF
        state.buttons.UP = self._report[1] == 0x00
        state.buttons.DOWN = self._report[1] == 0xFF

        state.buttons.X = bool(self._report[5] & 0x10)
        state.buttons.A = bool(self._report[5] & 0x20)
        state.buttons.B = bool(self._report[5] & 0x40)
        state.buttons.Y = bool(self._report[5] & 0x80)
        state.buttons.L1 = bool(self._report[6] & 0x01)
        state.buttons.R1 = bool(self._report[6] & 0x02)
        state.buttons.SELECT = bool(self._report[6] & 0x10)
        state.buttons.START = bool(self._report[6] & 0x20)


class Zero2Device(Device):  # 8BitDo
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, DEVICE_TYPE_ADAFRUIT_SNES, device_descriptor=device_descriptor, debug=debug
        )

    def _update_state(self, state: State) -> None:
        state.buttons.A = bool(self._report[0] & 0x01)
        state.buttons.B = bool(self._report[0] & 0x02)
        state.buttons.X = bool(self._report[0] & 0x08)
        state.buttons.Y = bool(self._report[0] & 0x10)
        state.buttons.L1 = bool(self._report[0] & 0x40)
        state.buttons.R1 = bool(self._report[0] & 0x80)
        state.buttons.SELECT = bool(self._report[1] & 0x04)
        state.buttons.START = bool(self._report[1] & 0x08)

        # 4-bit BCD
        state.buttons.UP = self._report[2] in {0x07, 0x00, 0x01}
        state.buttons.RIGHT = self._report[2] in {0x01, 0x02, 0x03}
        state.buttons.DOWN = self._report[2] in {0x03, 0x04, 0x05}
        state.buttons.LEFT = self._report[2] in {0x05, 0x06, 0x07}


class PowerAWiredDevice(Device):
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, DEVICE_TYPE_POWERA_WIRED, device_descriptor=device_descriptor, debug=debug
        )

    def _update_state(self, state: State) -> None:
        # Buttons are bitfield
        state.buttons.Y = bool(self._report[0] & 0x01)
        state.buttons.B = bool(self._report[0] & 0x02)
        state.buttons.A = bool(self._report[0] & 0x04)
        state.buttons.X = bool(self._report[0] & 0x08)
        state.buttons.L1 = bool(self._report[0] & 0x10)
        state.buttons.R1 = bool(self._report[0] & 0x20)
        state.buttons.SELECT = bool(self._report[1] & 0x01)
        state.buttons.START = bool(self._report[1] & 0x02)

        # 4-bit BCD
        state.buttons.UP = self._report[2] in {0x07, 0x00, 0x01}
        state.buttons.RIGHT = self._report[2] in {0x01, 0x02, 0x03}
        state.buttons.DOWN = self._report[2] in {0x03, 0x04, 0x05}
        state.buttons.LEFT = self._report[2] in {0x05, 0x06, 0x07}


def _create_device(
    device: usb.core.Device,
    device_type: int,
    device_descriptor: DeviceDescriptor = None,
    debug: bool = False,
):
    if device_type == DEVICE_TYPE_SWITCH_PRO:
        return SwitchProDevice(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == DEVICE_TYPE_XINPUT:
        return XInputDevice(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == DEVICE_TYPE_ADAFRUIT_SNES:
        return AdafruitSnesDevice(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == DEVICE_TYPE_8BITDO_ZERO2:
        return Zero2Device(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == DEVICE_TYPE_POWERA_WIRED:
        return PowerAWiredDevice(device, device_descriptor=device_descriptor, debug=debug)
    else:
        raise ValueError("Unknown device type")


_connected_devices = []
_failed_devices = []


def _find_device(port: int = None, debug: bool = False) -> Device:  # noqa: PLR0912
    for device in usb.core.find(find_all=True):
        device_id = (device.idVendor, device.idProduct)
        if (port,) + device_id in _connected_devices or device_id in _failed_devices:
            continue

        if port is not None:
            port_numbers = device.port_numbers
            if port != 1 and port_numbers is None:
                # Board does not have USB hub, but a port greater than 1 is requested
                continue
            if port_numbers is not None and port_numbers != (port,):
                # Board has USB hub, but device is not plugged into the specified port
                continue

        if debug:
            print(
                f"device found on port #{port:d}",
                {
                    "pid": hex(device.idProduct),
                    "vid": hex(device.idVendor),
                    "manufacturer": device.manufacturer,
                    "product": device.product,
                    "serial": device.serial_number,
                    "port": device.port_numbers,
                },
            )

        device_descriptor = DeviceDescriptor(device)
        if (
            device_type := _get_device_type(
                device, device_descriptor=device_descriptor, debug=debug
            )
        ) == DEVICE_TYPE_UNKNOWN:
            if debug:
                print("device not recognized")
            _failed_devices.append(device_id)
            continue
        elif debug:
            print(
                "device identified:",
                next((name for i, name in enumerate(DEVICE_NAMES) if i == device_type)),
            )

        try:
            # initialize device specific class
            gamepad_device = _create_device(device, device_type, device_descriptor, debug)

            # set player led (if supported)
            gamepad_device.led = port

            _connected_devices.append((port,) + device_id)
            return gamepad_device
        except ValueError:
            if debug:
                print("failed to initialize device")
            _failed_devices.append(device_id)


class Gamepad:
    """Helper class which coordinates device identification, initialization and reading for
    supported USB gamepad devices.
    """

    def __init__(self, port: int = None, debug: bool = False) -> None:
        """Initializes the :class:`Gamepad` device helper.

        :param port: If using a USB hub such as the CH334F, you can specify the desired physical
            port to communicate with. This is useful for reading from multiple gamepad devices with
            a specific device location for each. Use `None` to allow this class to communicate with
            devices on any USB port.
        :param debug: Set this value to `True` to generate verbose debug messages over REPL.
        """
        self._port = port
        self._debug = debug

        self._device = None
        self._device_id = None
        self._state = State()
        self._timeouts = 0

        self._timestamp = time.monotonic() - _SEARCH_DELAY

    def update(self) -> bool:
        """Update the gamepad device. If no device is current active, it will attempt to identify
        and connect with a USB device at most once every second. If a device is active, it will poll
        it and update the gamepad state. If the device is deemed that it is no longer responsive, it
        will be automatically disconnected.

        :return: Whether or not the state of the gamepad was updated.
        """
        if self._device is None and time.monotonic() - self._timestamp >= _SEARCH_DELAY:
            self._device = _find_device(self._port, debug=self._debug)
            if self._device is not None:
                self._device_id = self._device.device_id
            self._timestamp = time.monotonic()
        if self._device is None:
            return False

        try:
            return self._device.read_state(self._state)
        except usb.core.USBTimeoutError:
            self._timeouts += 1
            if self._timeouts > _MAX_TIMEOUTS:
                if self._debug:
                    print("device exceeded max timeouts")
                return self.disconnect()
        except usb.core.USBError:
            if self._debug:
                print("encountered error")
            return self.disconnect()
        return False

    @property
    def events(self) -> tuple:
        """A tuple of all changed button states since the last successful update as
        :class:`keypad.Event` objects. The :attr:`keypad.Event.key_number` value represents the
        button ID.
        """
        return self._state.buttons.events

    @property
    def port(self) -> int:
        """The designated port number when the gamepad was initialized."""
        return self._port

    @property
    def connected(self) -> bool:
        """Whether or not a usb gamepad device is connected."""
        return self._device is not None

    @property
    def device_type(self) -> int:
        """The id of the device type if a usb gamepad device is connected. Otherwise, it
        will be :const:`DEVICE_TYPE_UNKNOWN`.
        """
        return self._device.device_id if self._device is not None else DEVICE_TYPE_UNKNOWN

    @property
    def buttons(self) -> Buttons:
        """The object which handles the state of all digital button inputs."""
        return self._state.buttons

    @property
    def left_trigger(self) -> float:
        """The value of the analog left trigger from 0.0 to 1.0."""
        return self._state.left_trigger

    @property
    def right_trigger(self) -> float:
        """The value of the analog right trigger from 0.0 to 1.0."""
        return self._state.right_trigger

    @property
    def left_joystick(self) -> tuple:
        """The position of the left analog joystick on each axis from -1.0 to 1.0 represented as a
        tuple with the format (x, y).
        """
        return self._state.left_joystick

    @property
    def right_joystick(self) -> tuple:
        """The position of the right analog joystick on each axis from -1.0 to 1.0 represented as a
        tuple with the format (x, y).
        """
        return self._state.right_joystick

    def disconnect(self) -> bool:
        """Disconnect from the usb gamepad device if one is currently active.

        :return: If there is no active device, it will return `False`. Otherwise, `True`.
        """
        if self._device is None:
            return False
        if self._debug:
            print("disconnecting from device:", self._device_id)
        if (self._port,) + self._device_id in _connected_devices:
            _connected_devices.remove((self._port,) + self._device_id)
        del self._device
        self._device = None
        self._device_id = None
        self._timeouts = 0
        self._state.reset()
        return True
