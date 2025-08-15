# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
# SPDX-FileCopyrightText: Copyright (c) 2025 Sam Blenny
#
# SPDX-License-Identifier: MIT
"""
`usb_host_gamepad`
================================================================================

CircuitPython USB host driver for game controller devices.


* Author(s): Cooper Dalrymple

Implementation Notes
--------------------

**Hardware:**

.. todo:: Add links to any specific hardware product page(s), or category page(s).
  Use unordered list & hyperlink rST inline format: "* `Link Text <url>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

.. todo:: Uncomment or remove the Bus Device and/or the Register library dependencies
  based on the library's use of either.

# * Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# * Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

# imports

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/relic-se/CircuitPython_USB_Host_Gamepad.git"

import keypad
from micropython import const
import time
import usb.core

import adafruit_usb_host_descriptors

# Gamepad button bitmask constants

UP     = const(0x0001)  # dpad: Up
DOWN   = const(0x0002)  # dpad: Down
LEFT   = const(0x0004)  # dpad: Left
RIGHT  = const(0x0008)  # dpad: Right
START  = const(0x0010)
SELECT = const(0x0020)
L      = const(0x0100)  # Left shoulder button
R      = const(0x0200)  # Right shoulder button
B      = const(0x1000)  # button cluster: bottom button (Nintendo B, Xbox A)
A      = const(0x2000)  # button cluster: right button  (Nintendo A, Xbox B)
Y      = const(0x4000)  # button cluster: left button   (Nintendo Y, Xbox X)
X      = const(0x8000)  # button cluster: top button    (Nintendo X, Xbox Y)

KEYS = (
    UP, DOWN, LEFT, RIGHT,
    START, SELECT,
    L, R,
    B, A, Y, X,
)

# USB detected device types

DEVICE_TYPE_UNKNOWN       = const(0)
DEVICE_TYPE_SWITCH_PRO    = const(1)  # 057e:2009 clones of Switch Pro Controller
DEVICE_TYPE_ADAFRUIT_SNES = const(2)  # 081f:e401 generic SNES layout HID, low-speed
DEVICE_TYPE_8BITDO_ZERO2  = const(3)  # 2dc8:9018 mini SNES layout, HID over USB-C
DEVICE_TYPE_XINPUT        = const(4)  # (vid:pid vary) Clones of Xbox360 controller
DEVICE_TYPE_BOOT_KEYBOARD = const(5)
DEVICE_TYPE_POWERA_WIRED  = const(6)  # 20d6:a711 PowerA Wired Controller (for Switch)

DEVICE_TYPES = (
    # (index, vid, pid),
    (DEVICE_TYPE_SWITCH_PRO, 0x057e, 0x2009),
    (DEVICE_TYPE_ADAFRUIT_SNES, 0x081f, 0xe401),
    (DEVICE_TYPE_8BITDO_ZERO2, 0x2dc8, 0x9018),
    (DEVICE_TYPE_POWERA_WIRED, 0x20d6, 0xa711),
)

DEVICE_CLASSES = (
    # (index, device class, device subclass, interface 0 class, interface 0 subclass),
    (DEVICE_TYPE_XINPUT, 0xff, 0xff, 0xff, 0x5d),
    (DEVICE_TYPE_BOOT_KEYBOARD, 0x00, 0x00, 0x03, 0x01),
)

DEVICE_NAMES = (
    (DEVICE_TYPE_UNKNOWN, "Unknown"),
    (DEVICE_TYPE_SWITCH_PRO, "Switch Pro Controller"),
    (DEVICE_TYPE_ADAFRUIT_SNES, "Adafruit SNES Controller"),
    (DEVICE_TYPE_8BITDO_ZERO2, "8BitDo Zero 2"),
    (DEVICE_TYPE_XINPUT, "Generic XInput"),
    (DEVICE_TYPE_BOOT_KEYBOARD, "Generic Boot Keyboard"),
    (DEVICE_TYPE_POWERA_WIRED, "PowerA Wired Controller"),
)

MAX_TIMEOUTS = const(99)
SEARCH_DELAY = const(1)

class Descriptor:

    def __init__(self, descriptor:bytearray, length:int=None, descriptor_type:int=None):
        if (
            (length is not None and len(descriptor) != length) or
            descriptor[0] != len(descriptor) or
            (descriptor_type is not None and descriptor[1] != descriptor_type)
        ):
            raise ValueError("Invalid descriptor format")

class EndpointDescriptor(Descriptor):

    def __init__(self, descriptor:bytearray):
        super().__init__(descriptor, 7, adafruit_usb_host_descriptors.DESC_ENDPOINT)
        self.address         = descriptor[2]
        self.attributes      = descriptor[3]
        self.max_packet_size = (descriptor[5] << 8) | descriptor[4]
        self.interval        = descriptor[6]

    @property
    def input(self) -> bool:
        return bool(self.address & 0x80)
    
    @property
    def output(self) -> bool:
        return not self.input
    
    def __str__(self):
        return str({
            "address": hex(self.address),
            "attributes": hex(self.attributes),
            "max_packet_size": self.max_packet_size,
            "interval": self.interval,
            "input": self.input,
            "output": self.output,
        })

class InterfaceDescriptor(Descriptor):

    def __init__(self, descriptor:bytearray):
        super().__init__(descriptor, 9, adafruit_usb_host_descriptors.DESC_INTERFACE)
        self.index              = descriptor[2]
        self.endpoints          = descriptor[4]
        self.interface_class    = descriptor[5]
        self.interface_subclass = descriptor[6]
        self.protocol           = descriptor[7]

        self.endpoint = []

    def append_endpoint(self, descriptor:bytearray) -> None:
        self.endpoint.append(EndpointDescriptor(descriptor))

    @property
    def in_endpoint(self) -> EndpointDescriptor:
        try:
            return next((x for x in self.endpoint if x.input))
        except StopIteration:
            return None
    
    @property
    def out_endpoint(self) -> EndpointDescriptor:
        try:
            return next((x for x in self.endpoint if x.output))
        except StopIteration:
            return None
    
    def get_class_identifier(self) -> tuple:
        return (self.interface_class, self.interface_subclass)
    
    def __str__(self):
        return str({
            "class":     hex(self.interface_class),
            "subclass":  hex(self.interface_subclass),
            "protocol":  hex(self.protocol),
            "endpoints": self.endpoints,
        })
        

class ConfigurationDescriptor(Descriptor):

    def __init__(self, device:usb.core.Device, configuration:int=0):
        config_descriptor = adafruit_usb_host_descriptors.get_configuration_descriptor(device, configuration)

        self.interface = []

        interface_index = None
        i = 0
        while i < len(config_descriptor):
            descriptor_len, descriptor_type = config_descriptor[i:i+2]
            descriptor = config_descriptor[i:i+descriptor_len]

            if descriptor_type == adafruit_usb_host_descriptors.DESC_CONFIGURATION:
                super().__init__(descriptor, 9, adafruit_usb_host_descriptors.DESC_CONFIGURATION)
                self.interfaces = descriptor[4]
                self.value      = descriptor[5]  # for set_configuration()
                self._max_power = descriptor[8]

            elif descriptor_type == adafruit_usb_host_descriptors.DESC_INTERFACE:
                interface_index = len(self.interface)
                self.interface.append(InterfaceDescriptor(descriptor))
                
            elif descriptor_type == adafruit_usb_host_descriptors.DESC_ENDPOINT and interface_index is not None:
                self.interface[interface_index].append_endpoint(descriptor)
            
            i += descriptor_len

    @property
    def max_power(self) -> int:
        return self._max_power * 2  # units are 2 mA

    def get_class_identifier(self, interface:int=0):
        return self.interface[interface].get_class_identifier()
    
    def __str__(self):
        return str({
            "value":      hex(self.value),
            "max_power":  f"{self.max_power} mA",
            "interfaces": self.interfaces,
        })

class DeviceDescriptor:

    def __init__(self, device:usb.core.Device):
        descriptor = adafruit_usb_host_descriptors.get_device_descriptor(device)
        self.device_class = descriptor[4]
        self.device_subclass = descriptor[5]
        self.protocol = descriptor[6]
        self.max_packet_size = descriptor[7]
        self.configurations = descriptor[17]

        self.configuration = []
        for i in range(self.configurations):
            self.configuration.append(ConfigurationDescriptor(device, i))

    def get_class_identifier(self, configuration:int=0, interface:int=0) -> tuple:
        return (self.device_class, self.device_subclass) + self.configuration[configuration].get_class_identifier(interface)
    
    def __str__(self):
        return str({
            "class":           hex(self.device_class),
            "subclass":        hex(self.device_subclass),
            "protocol":        hex(self.protocol),
            "max_packet_size": self.max_packet_size,
            "configurations":  self.configurations,
        })

def get_device_type(device:usb.core.Device, device_descriptor:DeviceDescriptor=None, debug:bool=False) -> int:
    # identify device by id
    device_id = (device.idVendor, device.idProduct)
    if debug:
        print("identifying device by id (vid+pid):", [hex(x) for x in device_id])
    for device_type, type_vid, type_pid in DEVICE_TYPES:
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
    for device_type, type_class, type_subclass, type_int_class, type_int_subclass in DEVICE_CLASSES:
        if class_identifier == (type_class, type_subclass, type_int_class, type_int_subclass):
            if debug:
                print("found device type:", device_type)
            return device_type
    
    return DEVICE_TYPE_UNKNOWN

def report_equals(a:bytearray, b:bytearray, length:int=None) -> bool:
    if a is None and b is not None or b is None and a is not None:
        return False
    
    if length is None:
        length = min(len(a), len(b))
    for i in range(length):
        if a[i] != b[i]:
            return False
    return True

class Device:

    def __init__(self, device:usb.core.Device, device_type:int, device_descriptor:DeviceDescriptor=None, configuration:int=0, interface:int=0, debug:bool=False):
        if interface != 0:
            raise ValueError("Only interface 0 is supported")
        
        self._device        = device
        self._device_type   = device_type
        self._led           = 0
        self._debug         = debug

        self._descriptor    = DeviceDescriptor(device) if device_descriptor is None else device_descriptor
        self._configuration = self._descriptor.configuration[configuration]
        self._interface     = self._configuration.interface[interface]
        self._in_endpoint   = self._interface.in_endpoint
        self._out_endpoint  = self._interface.out_endpoint
        if self._in_endpoint is None or self._out_endpoint is None:
            raise ValueError("invalid interface endpoints")

        # make sure CircuitPython core is not claiming the device
        if device.is_kernel_driver_active(interface):
            if debug:
                print("detaching device from kernel")
            device.detach_kernel_driver(interface)

        # set configuration
        device.set_configuration(self._configuration.value)

        self._max_packet_size = min(64, max(self._in_endpoint.max_packet_size, self._out_endpoint.max_packet_size))
        self._report = bytearray(self._max_packet_size)
        self._previous_report = bytearray(self._max_packet_size)

        # read idle state
        count = self.read()
        self._idle_report = self._report[:count]

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
    def led(self, value:int) -> None:
        self._led = value

    def read_state(self) -> int:
        packet_size = self.read()
        if report_equals(self._report, self._previous_report, packet_size) or report_equals(self._report, self._idle_report, packet_size):
            return
        self._previous_report = self._report[:]
        return self._get_state()

    def _get_state(self) -> int:
        return 0
    
    def write(self, data:bytearray, acknowledge:bool = True) -> bool:
        try:
            self._device.write(self._out_endpoint.address, data, timeout=self._out_endpoint.interval)
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
        count = self._device.read(self._in_endpoint.address, self._report, timeout=self._in_endpoint.interval)
        return count
    
    def flush(self) -> None:
        for i in range(8):
            try:
                self.read()
            except usb.core.USBTimeoutError:
                pass

class SwitchProDevice(Device):
    def __init__(self, device:usb.core.Device, device_descriptor:DeviceDescriptor=None, debug:bool=False):
        super().__init__(device, DEVICE_TYPE_SWITCH_PRO, device_descriptor=device_descriptor, debug=debug)

        # perform handshake
        for msg in (
            bytes(b'\x80\x01'),  # get device type and mac address
            bytes(b'\x80\x02'),  # handshake
            bytes(b'\x80\x03'),  # set faster baud rate
            bytes(b'\x80\x02'),  # handshake
            bytes(b'\x80\x04'),  # use USB HID only and disable timeout
            # set input report mode to standard
            bytes(b'\x01\x06\x00\x00\x00\x00\x00\x00\x00\x00\x03\x30'),
            # set home LED
            bytes(b'\x01\x0b\x00\x00\x00\x00\x00\x00\x00\x00\x38\x01\x00\x00\x11\x11'),
        ):
            if not self.write(msg):
                raise ValueError("SwitchPro HANDSHAKE GLITCH")

    @property
    def led(self) -> int:
        return self._led
    
    @led.setter
    def led(self, value:int) -> None:
        self._led = min(max(value, 0), 4)
        msg = bytearray(b'\x01\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x30\x00')
        for i in range(4):
            if self._led > i:
                msg[len(msg)-1] |= 1 << i
        self.write(msg)

    def _get_state(self) -> int:
        state = 0
        state |= Y      if self._report[2] & 0x01 else 0
        state |= X      if self._report[2] & 0x02 else 0
        state |= B      if self._report[2] & 0x04 else 0
        state |= A      if self._report[2] & 0x08 else 0
        state |= R      if self._report[2] & 0x40 else 0
        state |= SELECT if self._report[3] & 0x01 else 0
        state |= START  if self._report[3] & 0x02 else 0
        state |= DOWN   if self._report[4] & 0x01 else 0
        state |= UP     if self._report[4] & 0x02 else 0
        state |= RIGHT  if self._report[4] & 0x04 else 0
        state |= LEFT   if self._report[4] & 0x08 else 0
        state |= L      if self._report[4] & 0x40 else 0
        return state

class XInputDevice(Device):
    def __init__(self, device:usb.core.Device, device_descriptor:DeviceDescriptor=None, debug:bool=False):
        super().__init__(device, DEVICE_TYPE_XINPUT, device_descriptor=device_descriptor, debug=debug)
        self.flush()  # ignore initial reports before normal operation

    @property
    def led(self) -> int:
        return self._led
    
    @led.setter
    def led(self, value:int) -> None:
        self._led = min(max(value, 0), 2)
        msg = bytearray(b'\x01\x03\x02')
        for i in range(2):
            if self._led > i:
                msg[len(msg)-1] |= 1 << (1 - i)
        self.write(msg)

    def _get_state(self) -> int:
        state = 0
        state |= LEFT   if self._report[0] == 0x00 else 0
        state |= RIGHT  if self._report[0] == 0xff else 0
        state |= UP     if self._report[1] == 0x00 else 0
        state |= DOWN   if self._report[1] == 0xff else 0
        state |= A      if self._report[5] == 0x2f else 0
        state |= B      if self._report[5] == 0x4f else 0
        state |= X      if self._report[5] == 0x1f else 0
        state |= Y      if self._report[5] == 0x8f else 0
        state |= L      if self._report[6] == 0x01 else 0
        state |= R      if self._report[6] == 0x02 else 0
        state |= SELECT if self._report[6] == 0x10 else 0
        state |= START  if self._report[6] == 0x20 else 0
        return state

connected_devices = []
failed_devices = []
def find_device(port:int=None, debug:bool=False) -> Device:
    global connected_devices, failed_devices

    if port is not None and (port < 1 or port > 2):
        raise ValueError("Only ports 1-2 supported")

    for device in usb.core.find(find_all=True):
        device_id = (device.idVendor, device.idProduct)
        if device_id in connected_devices or device_id in failed_devices:
            continue

        if port is not None:
            port_numbers = device.port_numbers
            if port == 1 and port_numbers is not None and port_numbers != (1,):
                # Board has USB hub, but device is not plugged into port 1
                continue
            if port == 2 and (port_numbers is None or port_numbers != (2,)):
                # Board doesn't have a USB hub, or it has a hub but the device is not plugged into port 2
                continue

        if debug:
            print("device found on port #{:d}".format(port), {
                "pid": hex(device.idProduct),
                "vid": hex(device.idVendor),
                "manufacturer": device.manufacturer,
                "product": device.product,
                "serial": device.serial_number,
                "port": device.port_numbers,
            })
        
        device_descriptor = DeviceDescriptor(device)
        if (device_type := get_device_type(device, device_descriptor=device_descriptor, debug=debug)) == DEVICE_TYPE_UNKNOWN:
            if debug:
                print("device not recognized")
            failed_devices.append(device_id)
            continue
        elif debug:
            print("device identified:", next((name for x, name in DEVICE_NAMES if x == device_type)))

        try:
            # initialize device specific class
            if device_type == DEVICE_TYPE_SWITCH_PRO:
                device = SwitchProDevice(device, device_descriptor=device_descriptor, debug=debug)
            elif device_type == DEVICE_TYPE_XINPUT:
                device = XInputDevice(device, device_descriptor=device_descriptor, debug=debug)
            else:
                device = Device(device, device_type, device_descriptor=device_descriptor, debug=debug)

            # set player led (if supported)
            device.led = port

            connected_devices.append(device_id)
            return device
        except ValueError:
            if debug:
                print("failed to initialize device")
            failed_devices.append(device_id)

class Gamepad:
    
    def __init__(self, port:int=None, debug:bool=False) -> None:
        if port is not None and (port < 1 or port > 2):
            raise ValueError("Only ports 1-2 supported")
        
        self._port = port
        self._debug = debug

        self._device = None
        self._state = 0
        self._previous_state = 0
        self._timeouts = 0

        self._search_timestamp = 0

    def update(self) -> tuple:
        if self._device is None and time.monotonic() - self._search_timestamp >= SEARCH_DELAY:
            self._device = find_device(self._port, debug=self._debug)
            self._search_timestamp = time.monotonic()
        if self._device is None:
            return
        
        try:
            state = self._device.read_state()
            if state is not None:
                self._previous_state = self._state
                self._state = state
        except usb.core.USBTimeoutError:
            self._timeouts += 1
            if self._timeouts > MAX_TIMEOUTS:
                self.disconnect()
        except usb.core.USBError:
            self.disconnect()

    @property
    def events(self) -> tuple:
        self.update()
        events = []
        if self._state != self._previous_state:
            for key in KEYS:
                if (self._state & key) ^ (self._previous_state & key):
                    events.append(keypad.Event(key, self._state & key))
        return tuple(events)
    
    @property
    def port(self) -> int:
        return self._port
    
    @property
    def connected(self) -> bool:
        return self._device is not None
    
    @property
    def device_type(self) -> int:
        return DEVICE_TYPE_UNKNOWN
    
    @property
    def state(self) -> int:
        return self._state
    
    @property
    def UP(self) -> bool:
        return self._state & UP
    
    @property
    def DOWN(self) -> bool:
        return self._state & DOWN
    
    @property
    def LEFT(self) -> bool:
        return self._state & LEFT
    
    @property
    def RIGHT(self) -> bool:
        return self._state & RIGHT
    
    @property
    def START(self) -> bool:
        return self._state & START
    
    @property
    def SELECT(self) -> bool:
        return self._state & SELECT
    
    @property
    def L(self) -> bool:
        return self._state & L
    
    @property
    def R(self) -> bool:
        return self._state & R
    
    @property
    def B(self) -> bool:
        return self._state & B
    
    @property
    def A(self) -> bool:
        return self._state & A
    
    @property
    def Y(self) -> bool:
        return self._state & Y
    
    @property
    def X(self) -> bool:
        return self._state & X
    
    def disconnect(self) -> None:
        global connected_devices
        if self._device is not None:
            device_id = self._device.device_id
            if device_id in connected_devices:
                connected_devices.remove(self._device.device_id)
            del self._device
            self._device = None
            self._state = 0
            self._timeouts = 0
    