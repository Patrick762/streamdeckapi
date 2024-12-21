[![PyPI version](https://badge.fury.io/py/streamdeckapi.svg)](https://badge.fury.io/py/streamdeckapi)

# streamdeckapi
Stream Deck API Library for Home Assistant Stream Deck Integration

Only compatible with separate [Stream Deck Plugin](https://github.com/Patrick762/streamdeckapi-plugin) or the bundled server.

## Server inside docker container
The docker image allows you to use the streamdeckapi server inside a docker container.

### Usage
```shell
docker run -v /dev/hidraw7:/dev/hidraw7 -p 6153:6153 --privileged ghcr.io/patrick762/streamdeckapi:main
```

**Note:** You have to change `hidraw7` to the path of your Stream Deck. You can find this path by using `lshid` (https://pypi.org/project/lshid/).

## Limitations
- No zeroconf discovery
- No `doubleTap` event

## Server without docker
This library also contains a server to use the streamdeck with Linux or without the official Stream Deck Software.

For this to work, the following software is required:

- LibUSB HIDAPI [Installation instructions](https://python-elgato-streamdeck.readthedocs.io/en/stable/pages/backend_libusb_hidapi.html) or [Installation instructions](https://github.com/jamesridgway/devdeck/wiki/Installation)
- cairo [Installation instructions for Windows](https://stackoverflow.com/a/73913080)

Cairo Installation for Windows:
```bash
pip install pipwin

pipwin install cairocffi
```

### Limitations
- No `doubleTap` event

### Installation on Linux / Raspberry Pi

Install requirements:
`sudo apt install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 libjpeg-dev zlib1g-dev libopenjp2-7 libtiff5 libgtk-3-dev python3-pip`

Allow all users non-root access to Stream Deck Devices:
```bash
sudo tee /etc/udev/rules.d/10-streamdeck.rules << EOF
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"
EOF
```

Reload access rules:
`sudo udevadm control --reload-rules`

Install the package:
`pip install streamdeckapi`

Reboot your system

Start the server:
`streamdeckapi-server`

### Example service
To run the server on startup, you can use the following config in the file `/etc/systemd/system/streamdeckapi.service`:

```conf
[Unit]
Description=Stream Deck API Service
Wants=network-online.target
After=network.target

[Service]
WorkingDirectory=/home/pi
ExecStart=/home/pi/.local/bin/streamdeckapi-server
User=pi
StandardOutput=console

[Install]
WantedBy=multi-user.target
```

To start the service, run `sudo systemctl start streamdeckapi.service`.

To enable the service, run `sudo systemctl enable streamdeckapi.service`.
