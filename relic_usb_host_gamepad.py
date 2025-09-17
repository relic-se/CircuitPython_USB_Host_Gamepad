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

_DEVICE_TYPE_UNKNOWN = const(0)
_DEVICE_TYPE_SWITCH_PRO = const(1)  # 057e:2009 clones of Switch Pro Controller
_DEVICE_TYPE_ADAFRUIT_SNES = const(2)  # 081f:e401 generic SNES layout HID, low-speed
_DEVICE_TYPE_8BITDO_ZERO2 = const(3)  # 2dc8:9018 mini SNES layout, HID over USB-C
_DEVICE_TYPE_XINPUT = const(4)  # (vid:pid vary) Clones of Xbox360 controller
_DEVICE_TYPE_POWERA_WIRED = const(5)  # 20d6:a711 PowerA Wired Controller (for Switch)

_DEVICE_TYPES = (
    # (index, vid, pid),
    (_DEVICE_TYPE_SWITCH_PRO, 0x057E, 0x2009),
    (_DEVICE_TYPE_ADAFRUIT_SNES, 0x081F, 0xE401),
    (_DEVICE_TYPE_8BITDO_ZERO2, 0x2DC8, 0x9018),
    (_DEVICE_TYPE_POWERA_WIRED, 0x20D6, 0xA711),
)

_DEVICE_CLASSES = (
    # (index, device class, device subclass, interface 0 class, interface 0 subclass),
    (_DEVICE_TYPE_XINPUT, 0xFF, 0xFF, 0xFF, 0x5D),
)

_DEVICE_NAMES = (
    (_DEVICE_TYPE_UNKNOWN, "Unknown"),
    (_DEVICE_TYPE_SWITCH_PRO, "Switch Pro Controller"),
    (_DEVICE_TYPE_ADAFRUIT_SNES, "Adafruit SNES Controller"),
    (_DEVICE_TYPE_8BITDO_ZERO2, "8BitDo Zero 2"),
    (_DEVICE_TYPE_XINPUT, "Generic XInput"),
    (_DEVICE_TYPE_POWERA_WIRED, "PowerA Wired Controller"),
)

_BUTTON_NAMES = (
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


class Button:
    A = const(0)
    B = const(1)
    X = const(2)
    Y = const(3)
    UP = const(4)
    DOWN = const(5)
    LEFT = const(6)
    RIGHT = const(7)
    START = const(8)
    SELECT = const(9)
    HOME = const(10)
    L1 = const(11)
    R1 = const(12)
    L2 = const(13)
    R2 = const(14)
    L3 = const(15)
    R3 = const(16)
    JOYSTICK_UP = const(17)
    JOYSTICK_DOWN = const(18)
    JOYSTICK_LEFT = const(19)
    JOYSTICK_RIGHT = const(20)

    def __init__(self, value: int, pressed: bool = False):
        assert self.A <= value <= self.JOYSTICK_RIGHT
        self._value = value
        self._pressed = pressed
        self._changed = False

    def __str__(self) -> str:
        return " ".join((_BUTTON_NAMES[self._value], "Pressed" if self._pressed else "Released"))

    def __hash__(self) -> int:
        return self.__value

    def __eq__(self, other) -> bool:
        if type(other) is int:
            return self._value == other
        else:
            return self._value == other._value

    @property
    def value(self) -> int:
        return self._value

    @property
    def pressed(self) -> bool:
        return self._pressed

    @pressed.setter
    def pressed(self, value: bool) -> None:
        self._changed = self._pressed != value
        self._pressed = value

    @property
    def released(self) -> bool:
        return not self._pressed

    @released.setter
    def released(self, value: bool) -> None:
        self.pressed = not value

    @property
    def changed(self) -> bool:
        return self._changed


class Buttons:
    def __init__(self):
        self.A = Button(Button.A)
        self.B = Button(Button.B)
        self.X = Button(Button.X)
        self.Y = Button(Button.Y)
        self.UP = Button(Button.UP)
        self.DOWN = Button(Button.DOWN)
        self.LEFT = Button(Button.LEFT)
        self.RIGHT = Button(Button.RIGHT)
        self.START = Button(Button.START)
        self.SELECT = Button(Button.SELECT)
        self.HOME = Button(Button.HOME)
        self.L1 = Button(Button.L1)
        self.R1 = Button(Button.R1)
        self.L2 = Button(Button.L2)
        self.R2 = Button(Button.R2)
        self.L3 = Button(Button.L3)
        self.R3 = Button(Button.R3)
        self.JOYSTICK_UP = Button(Button.JOYSTICK_UP)
        self.JOYSTICK_DOWN = Button(Button.JOYSTICK_DOWN)
        self.JOYSTICK_LEFT = Button(Button.JOYSTICK_LEFT)
        self.JOYSTICK_RIGHT = Button(Button.JOYSTICK_RIGHT)

    def __iter__(self):
        for x in _BUTTON_NAMES:
            yield getattr(self, x)

    def __getitem__(self, index: int) -> Button:
        return getattr(self, _BUTTON_NAMES[index])

    def __len__(self) -> int:
        return len(_BUTTON_NAMES)

    def get_changed(self) -> tuple:
        return tuple([x for x in self if x.changed])

    def is_changed(self) -> bool:
        try:
            next(x for x in self if x.changed)
        except StopIteration:
            return False
        finally:
            return True


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
        self._buttons.L2.pressed = self._left_trigger >= _TRIGGER_THRESHOLD

    @property
    def right_trigger(self) -> float:
        return self._right_trigger / 255

    @right_trigger.setter
    def right_trigger(self, value: int | float) -> None:
        if type(value) is float:
            value = int(value * 255)
        self._right_trigger = min(max(value, 0), 255)
        self._buttons.R2.pressed = self._right_trigger >= _TRIGGER_THRESHOLD

    @property
    def left_joystick(self) -> tuple:
        return (self._left_joystick_x / 32768, self._left_joystick_y / 32768)

    @left_joystick.setter
    def left_joystick(self, value: tuple) -> None:
        if len(value) != 2:
            raise ValueError("value must be in the format of (x, y)")

        x, y = value
        if type(x) is float:
            x = int(x * 32767)
        if type(y) is float:
            y = int(y * 32767)
        self._left_joystick_x = min(max(x, -32768), 32767)
        self._left_joystick_y = min(max(y, -32768), 32767)

        self._buttons.JOYSTICK_RIGHT.pressed = self._left_joystick_x >= _JOYSTICK_THRESHOLD
        self._buttons.JOYSTICK_LEFT.pressed = self._left_joystick_x <= -_JOYSTICK_THRESHOLD
        self._buttons.JOYSTICK_UP.pressed = self._left_joystick_y >= _JOYSTICK_THRESHOLD
        self._buttons.JOYSTICK_DOWN.pressed = self._left_joystick_y <= -_JOYSTICK_THRESHOLD

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
        for button in self._buttons:
            button.pressed = False
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
    for device_type, type_class, type_subclass, type_int_class, type_int_subclass in _DEVICE_CLASSES:
        if class_identifier == (type_class, type_subclass, type_int_class, type_int_subclass):
            if debug:
                print("found device type:", device_type)
            return device_type

    return _DEVICE_TYPE_UNKNOWN


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
            except usb.core.USBTimeoutError:
                pass
        return False

    def read(self) -> tuple:
        count = self._device.read(self._in_endpoint.address, self._report, timeout=self._interval)
        return count

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
            device, _DEVICE_TYPE_SWITCH_PRO, device_descriptor=device_descriptor, debug=debug
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
        state.buttons.Y.pressed = bool(self._report[2] & 0x01)
        state.buttons.X.pressed = bool(self._report[2] & 0x02)
        state.buttons.B.pressed = bool(self._report[2] & 0x04)
        state.buttons.A.pressed = bool(self._report[2] & 0x08)
        state.buttons.R1.pressed = bool(self._report[2] & 0x40)
        state.buttons.SELECT.pressed = bool(self._report[3] & 0x01)
        state.buttons.START.pressed = bool(self._report[3] & 0x02)
        state.buttons.DOWN.pressed = bool(self._report[4] & 0x01)
        state.buttons.UP.pressed = bool(self._report[4] & 0x02)
        state.buttons.RIGHT.pressed = bool(self._report[4] & 0x04)
        state.buttons.LEFT.pressed = bool(self._report[4] & 0x08)
        state.buttons.L1.pressed = bool(self._report[4] & 0x40)


class XInputDevice(Device):
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, _DEVICE_TYPE_XINPUT, device_descriptor=device_descriptor, debug=debug
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
        state.buttons.UP.pressed = bool(self._report[2] & 0x01)
        state.buttons.DOWN.pressed = bool(self._report[2] & 0x02)
        state.buttons.LEFT.pressed = bool(self._report[2] & 0x04)
        state.buttons.RIGHT.pressed = bool(self._report[2] & 0x08)
        state.buttons.START.pressed = bool(self._report[2] & 0x10)
        state.buttons.SELECT.pressed = bool(self._report[2] & 0x20)
        state.buttons.L1.pressed = bool(self._report[3] & 0x01)
        state.buttons.R1.pressed = bool(self._report[3] & 0x02)
        state.buttons.HOME.pressed = bool(self._report[3] & 0x04)
        state.buttons.B.pressed = bool(self._report[3] & 0x10)
        state.buttons.A.pressed = bool(self._report[3] & 0x20)
        state.buttons.Y.pressed = bool(self._report[3] & 0x40)
        state.buttons.X.pressed = bool(self._report[3] & 0x80)

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
            device, _DEVICE_TYPE_ADAFRUIT_SNES, device_descriptor=device_descriptor, debug=debug
        )

    def _update_state(self, state: State) -> None:
        state.buttons.LEFT.pressed = self._report[0] == 0x00
        state.buttons.RIGHT.pressed = self._report[0] == 0xFF
        state.buttons.UP.pressed = self._report[1] == 0x00
        state.buttons.DOWN.pressed = self._report[1] == 0xFF

        state.buttons.X.pressed = bool(self._report[5] & 0x10)
        state.buttons.A.pressed = bool(self._report[5] & 0x20)
        state.buttons.B.pressed = bool(self._report[5] & 0x40)
        state.buttons.Y.pressed = bool(self._report[5] & 0x80)
        state.buttons.L1.pressed = bool(self._report[6] & 0x01)
        state.buttons.R1.pressed = bool(self._report[6] & 0x02)
        state.buttons.SELECT.pressed = bool(self._report[6] & 0x10)
        state.buttons.START.pressed = bool(self._report[6] & 0x20)


class Zero2Device(Device):  # 8BitDo
    def __init__(
        self,
        device: usb.core.Device,
        device_descriptor: DeviceDescriptor = None,
        debug: bool = False,
    ):
        super().__init__(
            device, _DEVICE_TYPE_ADAFRUIT_SNES, device_descriptor=device_descriptor, debug=debug
        )

    def _update_state(self, state: State) -> None:
        state.buttons.A.pressed = bool(self._report[0] & 0x01)
        state.buttons.B.pressed = bool(self._report[0] & 0x02)
        state.buttons.X.pressed = bool(self._report[0] & 0x08)
        state.buttons.Y.pressed = bool(self._report[0] & 0x10)
        state.buttons.L1.pressed = bool(self._report[0] & 0x40)
        state.buttons.R1.pressed = bool(self._report[0] & 0x80)
        state.buttons.SELECT.pressed = bool(self._report[1] & 0x04)
        state.buttons.START.pressed = bool(self._report[1] & 0x08)

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
            device, _DEVICE_TYPE_POWERA_WIRED, device_descriptor=device_descriptor, debug=debug
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
    if device_type == _DEVICE_TYPE_SWITCH_PRO:
        return SwitchProDevice(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == _DEVICE_TYPE_XINPUT:
        return XInputDevice(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == _DEVICE_TYPE_ADAFRUIT_SNES:
        return AdafruitSnesDevice(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == _DEVICE_TYPE_8BITDO_ZERO2:
        return Zero2Device(device, device_descriptor=device_descriptor, debug=debug)
    elif device_type == _DEVICE_TYPE_POWERA_WIRED:
        return PowerAWiredDevice(device, device_descriptor=device_descriptor, debug=debug)
    else:
        raise ValueError("Unknown device type")


_connected_devices = []
_failed_devices = []


def _find_device(port: int = None, debug: bool = False) -> Device:  # noqa: PLR0912
    if port is not None and (port < 1 or port > 2):
        raise ValueError("Only ports 1-2 supported")

    for device in usb.core.find(find_all=True):
        device_id = (device.idVendor, device.idProduct)
        if (port,) + device_id in _connected_devices or device_id in _failed_devices:
            continue

        if port is not None:
            port_numbers = device.port_numbers
            if port == 1 and port_numbers is not None and port_numbers != (1,):
                # Board has USB hub, but device is not plugged into port 1
                continue
            if port == 2 and (port_numbers is None or port_numbers != (2,)):
                # Board doesn't have a USB hub,or it has a hub but the device is not plugged into
                # port 2
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
            device_type := _get_device_type(device, device_descriptor=device_descriptor, debug=debug)
        ) == _DEVICE_TYPE_UNKNOWN:
            if debug:
                print("device not recognized")
            _failed_devices.append(device_id)
            continue
        elif debug:
            print(
                "device identified:", next((name for x, name in _DEVICE_NAMES if x == device_type))
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
    def __init__(self, port: int = None, debug: bool = False) -> None:
        if port is not None and (port < 1 or port > 2):
            raise ValueError("Only ports 1-2 supported")

        self._port = port
        self._debug = debug

        self._device = None
        self._device_id = None
        self._state = State()
        self._timeouts = 0

        self._timestamp = time.monotonic() - _SEARCH_DELAY

    def update(self) -> bool:
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
        events = []
        if self.update():
            for button in self._state.buttons.get_changed():
                events.append(keypad.Event(button.value, button.pressed))
        return tuple(events)

    @property
    def port(self) -> int:
        return self._port

    @property
    def connected(self) -> bool:
        return self._device is not None

    @property
    def device_type(self) -> int:
        return _DEVICE_TYPE_UNKNOWN

    @property
    def buttons(self) -> Buttons:
        return self._state.buttons

    @property
    def left_trigger(self) -> float:
        return self._state.left_trigger

    @property
    def right_trigger(self) -> float:
        return self._state.right_trigger

    @property
    def left_joystick(self) -> tuple:
        return self._state.left_joystick

    @property
    def right_joystick(self) -> tuple:
        return self._state.right_joystick

    def disconnect(self) -> bool:
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
