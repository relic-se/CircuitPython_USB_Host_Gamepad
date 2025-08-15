# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: Unlicense
import usb.core
import usb_host_gamepad

for i, device in enumerate(usb.core.find(find_all=True)):
    descriptor = usb_host_gamepad.DeviceDescriptor(device)
    print(f"Device {i}:", descriptor)
    for j, configuration in enumerate(descriptor.configuration):
        print(f"Configuration {j}:", configuration)
        for k, interface in enumerate(configuration.interface):
            print(f"Interface {k}:", interface)
            for l, endpoint in enumerate(interface.endpoint):
                print(f"Endpoint {l}:", endpoint)
