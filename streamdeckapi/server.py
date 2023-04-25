"""Stream Deck API Server."""

from StreamDeck.DeviceManager import DeviceManager
from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT

# Prints diagnostic information about a given StreamDeck.
def print_deck_info(index, deck):
    image_format = deck.key_image_format()

    flip_description = {
        (False, False): "not mirrored",
        (True, False): "mirrored horizontally",
        (False, True): "mirrored vertically",
        (True, True): "mirrored horizontally/vertically",
    }

    print("Deck {} - {}.".format(index, deck.deck_type()))
    print("\t - ID: {}".format(deck.id()))
    print("\t - Serial: '{}'".format(deck.get_serial_number()))
    print("\t - Firmware Version: '{}'".format(deck.get_firmware_version()))
    print("\t - Key Count: {} (in a {}x{} grid)".format(
        deck.key_count(),
        deck.key_layout()[0],
        deck.key_layout()[1]))
    if deck.is_visual():
        print("\t - Key Images: {}x{} pixels, {} format, rotated {} degrees, {}".format(
            image_format['size'][0],
            image_format['size'][1],
            image_format['format'],
            image_format['rotation'],
            flip_description[image_format['flip']]))
    else:
        print("\t - No Visual Output")

def start():
    streamdecks = DeviceManager().enumerate()

    print("Found {} Stream Deck(s).\n".format(len(streamdecks)))

    print("Started Stream Deck API server on port", PLUGIN_PORT)

    for index, deck in enumerate(streamdecks):
        deck.open()
        deck.reset()

        print_deck_info(index, deck)

        deck.close()
