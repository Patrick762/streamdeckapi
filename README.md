[![PyPI version](https://badge.fury.io/py/streamdeckapi.svg)](https://badge.fury.io/py/streamdeckapi)

# streamdeckapi
Stream Deck API Library for Home Assistant Stream Deck Integration

Only compatible with separate [Stream Deck Plugin](https://github.com/Patrick762/streamdeckapi-plugin) or the bundled server.

## Requirements
- Python 3.10 or higher

## Dependencies
- [websockets](https://pypi.org/project/websockets/) 11.0.2


## Server
This library also contains a server to use the streamdeck with Linux or without the official Stream Deck Software.

For this to work, the following software is required:

- LibUSB HIDAPI [Installation instructions](https://python-elgato-streamdeck.readthedocs.io/en/stable/pages/backend_libusb_hidapi.html) or [Installation instructions](https://github.com/jamesridgway/devdeck/wiki/Installation)
- cairo [Installation instructions for Windows](https://stackoverflow.com/a/73913080)

The event `doubleTap` is not working with this server software.
