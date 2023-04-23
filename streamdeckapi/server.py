"""Stream Deck API Server."""

from StreamDeck.DeviceManager import DeviceManager
from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT

def start():
    streamdecks = DeviceManager().enumerate()

    print("Found {} Stream Deck(s).\n".format(len(streamdecks)))

    print("Started Stream Deck API server on port", PLUGIN_PORT)
