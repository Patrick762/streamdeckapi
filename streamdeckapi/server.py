"""Stream Deck API Server."""

import re
import aiohttp
import asyncio
import platform
import human_readable_ids as hri
from jsonpickle import encode
from aiohttp import web
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices.StreamDeck import StreamDeck

from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT
from streamdeckapi.types import SDApplication, SDButton, SDButtonPosition, SDDevice


DEFAULT_ICON = re.sub(
    "\r\n|\n|\r",
    "",
    """
<svg xmlns="http://www.w3.org/2000/svg" height="144" width="144">
<rect width="144" height="144" fill="black" />
<circle cx="32" cy="72" r="10" fill="white" />
<circle cx="72" cy="72" r="10" fill="white" />
<circle cx="112" cy="72" r="10" fill="white" />
<text x="10" y="120" font-size="28px" fill="white">Configure</text>
</svg>
""",
)


application: SDApplication = SDApplication(
    {
        "font": "",
        "language": "",
        "platform": platform.system(),
        "platformVersion": platform.version(),
        "version": "0.0.1",
    }
)
devices: list[SDDevice] = []
buttons: dict[str, SDButton] = {}

# Examples
# devices.append(
#    SDDevice(
#        {
#            "id": "08B602C026FC8D1989FDF80EB8658612",
#            "name": "Stream Deck",
#            "size": {"columns": 5, "rows": 3},
#            "type": 0,
#        }
#    )
# )
# buttons["576e8e7fc6ac2a37fa436ed3dc76652b"] = SDButton(
#    {
#        "uuid": "kind-sloth-97",
#        "device": "08B602C026FC8D1989FDF80EB8658612",
#        "position": {"x": 0, "y": 0},
#        "svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72"><rect width="72" height="72" fill="#000" /><text text-anchor="middle" x="35" y="15" fill="#fff" font-size="12">off</text><text text-anchor="middle" x="35" y="65" fill="#fff" font-size="12">Philips Hue Huelight</text><g transform="translate(16, 12) scale(0.5)"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -512 512 512"><path fill="#e00" d="M256 -405Q215 -405 181 -385Q147 -365 127 -331Q107 -297 107 -256Q107 -219 124 -186.5Q141 -154 171 -134V-85Q171 -76 177 -70Q183 -64 192 -64H320Q329 -64 335 -70Q341 -76 341 -85V-134Q371 -154 388 -186.5Q405 -219 405 -256Q405 -297 385 -331Q365 -365 331 -385Q297 -405 256 -405ZM192 0Q192 9 198 15Q204 21 213 21H299Q308 21 314 15Q320 9 320 0V-21H192Z"/></svg></g></svg>',
#    }
# )


async def api_info_handler(
    request: web.Request,
):  # FIXME: can result in unparseable json (different keys, f.ex. x - x_pos)
    json_data = encode(
        {"devices": devices, "application": application, "buttons": buttons},
        unpicklable=False,
    )
    return web.Response(text=json_data, content_type="application/json")


async def api_icon_get_handler(request: web.Request):
    btnId = request.match_info["btnId"]
    for _, btn in buttons.items():
        if btn.uuid != btnId:
            continue
        return web.Response(text=btn.svg, content_type="image/svg+xml")
    return web.Response(status=404, text="Button not found")


async def api_icon_set_handler(request: web.Request):
    btnId = request.match_info["btnId"]
    if not request.has_body:
        return web.Response(status=422, text="No data in request")
    body = await request.text()
    print(body)
    if not body.startswith("<svg"):
        return web.Response(status=422, text="Only svgs are supported")
    btnKey = None
    for key, btn in buttons.items():
        if btn.uuid == btnId:
            btnKey = key
    if btnKey is None:
        return web.Response(status=404, text="Button not found")

    buttons[btnKey].svg = body

    return web.Response(text="Icon changed")


async def websocket_handler(request: web.Request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == "close":
                await ws.close()
            else:
                await ws.send_str("some websocket message payload")
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print("ws connection closed with exception %s" % ws.exception())
    return ws


def create_runner():
    app = web.Application()
    app.add_routes(
        [
            web.get("/", websocket_handler),
            web.get(PLUGIN_INFO, api_info_handler),
            web.get(PLUGIN_ICON + "/{btnId}", api_icon_get_handler),
            web.post(PLUGIN_ICON + "/{btnId}", api_icon_set_handler),
        ]
    )
    return web.AppRunner(app)


async def start_server(host="0.0.0.0", port=PLUGIN_PORT):
    runner = create_runner()
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print("Started Stream Deck API server on port", PLUGIN_PORT)


def get_position(deck: StreamDeck, key: int) -> SDButtonPosition:
    """Get the position of a key."""
    return SDButtonPosition({"x": int(key / deck.KEY_COLS), "y": key % deck.KEY_COLS})


def on_key_change(deck: StreamDeck, key: int, state: bool):
    """Handle key change callbacks."""
    position = get_position(deck, key)
    print(f"Key at {position.x_pos}|{position.y_pos} is state {state}")


def init_all():
    """Init Stream Deck devices."""
    # TODO: Load buttons from storage and save asap

    streamdecks: list[StreamDeck] = DeviceManager().enumerate()
    print("Found {} Stream Deck(s).\n".format(len(streamdecks)))

    for deck in streamdecks:
        if not deck.is_visual():
            continue

        deck.open()

        serial = deck.get_serial_number()

        devices.append(
            SDDevice(
                {
                    "id": serial,
                    "name": deck.deck_type(),
                    "size": {"columns": deck.KEY_COLS, "rows": deck.KEY_ROWS},
                    "type": 20,
                }
            )
        )

        for key in range(deck.key_count()):
            # FIXME: only add if not already in dict
            position = get_position(deck, key)
            buttons[key] = SDButton(
                {
                    "uuid": hri.get_new_id().lower().replace(" ", "-"),
                    "device": serial,
                    "position": {"x": position.x_pos, "y": position.y_pos},
                    "svg": DEFAULT_ICON,
                }
            )

        # TODO: write svg to buttons

        deck.set_key_callback(on_key_change)


def start():
    init_all()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server())
    loop.run_forever()
