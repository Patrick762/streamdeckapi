"""Stream Deck API Server."""

import re
import io
import asyncio
import platform
import sqlite3
import base64
import aiohttp
import human_readable_ids as hri
from jsonpickle import encode
from aiohttp import web
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices.StreamDeck import StreamDeck
from StreamDeck.ImageHelpers import PILHelper
import cairosvg
from PIL import Image
from ssdpy import SSDPServer

from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT, SD_SSDP
from streamdeckapi.types import SDApplication, SDButton, SDButtonPosition, SDDevice

# TODO: Websocket broadcast not working yet


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

#
#   Database
#

database = sqlite3.connect("streamdeckapi.db")
table_cursor = database.cursor()
table_cursor.execute("""
                CREATE TABLE IF NOT EXISTS buttons(
                   key integer PRIMARY KEY,
                   uuid text NOT NULL,
                   device text,
                   x integer,
                   y integer,
                   svg text
                )""")
table_cursor.close()


def save_button(key: int, button: SDButton):
    """Save button to database."""
    cursor = database.cursor()
    svg_bytes = button.svg.encode()
    base64_bytes = base64.b64encode(svg_bytes)
    base64_string = base64_bytes.decode()

    # Check if exists
    result = cursor.execute(f"SELECT uuid FROM buttons WHERE key={key}")
    matching_buttons = result.fetchall()
    if len(matching_buttons) > 0:
        # Perform update
        cursor.execute(
            f"UPDATE buttons SET svg=\"{base64_string}\" WHERE key={key}")
    else:
        # Create new row
        cursor.execute(
            f"INSERT INTO buttons VALUES ({key}, \"{button.uuid}\", \"{button.device}\", {button.position.x_pos}, {button.position.y_pos}, \"{base64_string}\")")
    database.commit()
    print(f"Saved button {button.uuid} with key {key} to database")
    cursor.close()


def get_button(key: int) -> SDButton | None:
    """Get a button from the database."""
    cursor = database.cursor()
    result = cursor.execute(
        f"SELECT key,uuid,device,x,y,svg FROM buttons WHERE key={key}")
    matching_buttons = result.fetchall()
    if len(matching_buttons) == 0:
        return None
    row = matching_buttons[0]
    base64_bytes = row[5].encode()
    svg_bytes = base64.b64decode(base64_bytes)
    svg_string = svg_bytes.decode()
    button = SDButton({
        "uuid": row[1],
        "device": row[2],
        "position": {"x": row[3], "y": row[4]},
        "svg": svg_string,
    })
    cursor.close()
    return button


def get_button_by_uuid(uuid: str) -> SDButton | None:
    """Get a button from the database."""
    cursor = database.cursor()
    result = cursor.execute(
        f"SELECT key,uuid,device,x,y,svg FROM buttons WHERE uuid=\"{uuid}\"")
    matching_buttons = result.fetchall()
    if len(matching_buttons) == 0:
        return None
    row = matching_buttons[0]
    base64_bytes = row[5].encode()
    svg_bytes = base64.b64decode(base64_bytes)
    svg_string = svg_bytes.decode()
    button = SDButton({
        "uuid": row[1],
        "device": row[2],
        "position": {"x": row[3], "y": row[4]},
        "svg": svg_string,
    })
    cursor.close()
    return button


def get_button_key(uuid: str) -> int:
    """Get a button key from the database."""
    cursor = database.cursor()
    result = cursor.execute(f"SELECT key FROM buttons WHERE uuid=\"{uuid}\"")
    matching_buttons = result.fetchall()
    if len(matching_buttons) == 0:
        return -1
    row = matching_buttons[0]
    key = row[0]
    cursor.close()
    return key


def get_buttons() -> dict[str, SDButton]:
    """Load all buttons from the database."""
    result: dict[str, SDButton] = {}
    cursor = database.cursor()
    for row in cursor.execute("SELECT key,uuid,device,x,y,svg FROM buttons"):
        base64_bytes = row[5].encode()
        svg_bytes = base64.b64decode(base64_bytes)
        svg_string = svg_bytes.decode()
        result[row[0]] = SDButton({
            "uuid": row[1],
            "device": row[2],
            "position": {"x": row[3], "y": row[4]},
            "svg": svg_string,
        })
    cursor.close()
    print(f"Loaded {len(result)} buttons from DB")
    return result


#
#   API
#


async def api_info_handler(_: web.Request):
    """Handle info requests."""
    json_data = encode(
        {"devices": devices, "application": application, "buttons": get_buttons()},
        unpicklable=False,
    )
    if not isinstance(json_data, str):
        return web.Response(status=500, text="jsonpickle error")
    json_data = (
        json_data.replace('"x_pos"', '"x"')
        .replace('"y_pos"', '"y"')
        .replace('"platform_version"', '"platformVersion"')
    )
    return web.Response(text=json_data, content_type="application/json")


async def api_icon_get_handler(request: web.Request):
    """Handle icon get requests."""
    uuid = request.match_info["uuid"]
    button = get_button_by_uuid(uuid)
    if button is None:
        return web.Response(status=404, text="Button not found")
    return web.Response(text=button.svg, content_type="image/svg+xml")


async def api_icon_set_handler(request: web.Request):
    """Handle icon set requests."""
    uuid = request.match_info["uuid"]
    if not request.has_body:
        return web.Response(status=422, text="No data in request")
    body = await request.text()
    if not body.startswith("<svg"):
        return web.Response(status=422, text="Only svgs are supported")
    button = get_button_by_uuid(uuid)
    if button is None:
        return web.Response(status=404, text="Button not found")

    # Update icon
    update_button_icon(uuid, body)

    print("Icon for button", uuid, "changed")

    return web.Response(text="Icon changed")


async def websocket_handler(request: web.Request):
    """Handle websocket."""
    web_socket = web.WebSocketResponse()
    await web_socket.prepare(request)
    async for msg in web_socket:
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == "close":
                await web_socket.close()
            else:
                await web_socket.send_str("some websocket message payload")
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print(
                f"Websocket connection closed with exception {web_socket.exception()}")
    return web_socket


#
#   Functions
#


def create_runner():
    """Create background runner"""
    app = web.Application()
    app.add_routes(
        [
            web.get("/", websocket_handler),
            web.get(PLUGIN_INFO, api_info_handler),
            web.get(PLUGIN_ICON + "/{uuid}", api_icon_get_handler),
            web.post(PLUGIN_ICON + "/{uuid}", api_icon_set_handler),
        ]
    )
    return web.AppRunner(app)


async def start_server(host="0.0.0.0", port=PLUGIN_PORT):
    """Start API server."""
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


def update_button_icon(uuid: str, svg: str):
    """Update a button icon."""
    streamdecks: list[StreamDeck] = DeviceManager().enumerate()
    for deck in streamdecks:
        if not deck.is_visual():
            continue

        deck.open()

        button = get_button_by_uuid(uuid)
        button_key = get_button_key(uuid)
        if button is not None and button_key >= 0:
            set_icon(deck, button_key, svg)
            button.svg = svg
            save_button(button_key, button)


def set_icon(deck: StreamDeck, key: int, svg: str):
    """Draw an icon to the button."""
    png_bytes = io.BytesIO()
    cairosvg.svg2png(svg.encode("utf-8"), write_to=png_bytes)
    
    # Debug
    cairosvg.svg2png(svg.encode("utf-8"), write_to=f"icon_{key}.png")

    icon = Image.open(png_bytes)
    image = PILHelper.create_scaled_image(deck, icon)

    deck.set_key_image(key, PILHelper.to_native_format(deck, image))


def init_all():
    """Init Stream Deck devices."""
    streamdecks: list[StreamDeck] = DeviceManager().enumerate()
    print(f"Found {len(streamdecks)} Stream Deck(s).")

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
            # Only add if not already in dict
            button = get_button(key)
            if button is None:
                position = get_position(deck, key)
                new_button = SDButton(
                    {
                        "uuid": hri.get_new_id().lower().replace(" ", "-"),
                        "device": serial,
                        "position": {"x": position.x_pos, "y": position.y_pos},
                        "svg": DEFAULT_ICON,
                    }
                )
                save_button(key, new_button)

        deck.reset()
        # Write svg to buttons
        for key, button in get_buttons().items():
            set_icon(deck, key, button.svg)

        deck.set_key_callback(on_key_change)


def start():
    """Entrypoint."""
    init_all()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server())
    loop.run_forever()

    # TODO: SSDP server
    server = SSDPServer(SD_SSDP)
    server.serve_forever()
