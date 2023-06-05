"""Stream Deck API Server."""

import re
import io
import asyncio
import platform
import sqlite3
import base64
import socket
from uuid import uuid4
from datetime import datetime
from multiprocessing import Process
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

from streamdeckapi.const import (
    DATETIME_FORMAT,
    DB_FILE,
    LONG_PRESS_SECONDS,
    PLUGIN_ICON,
    PLUGIN_INFO,
    PLUGIN_PORT,
    SD_SSDP
)
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
        "font": "Segoe UI",
        "language": "en",
        "platform": platform.system(),
        "platformVersion": platform.version(),
        "version": "0.0.1",
    }
)
devices: list[SDDevice] = []
websocket_connections: list[web.WebSocketResponse] = []

streamdecks: list[StreamDeck] = DeviceManager().enumerate()

#
#   Database
#

database_first = sqlite3.connect(DB_FILE)
table_cursor = database_first.cursor()
table_cursor.execute("""
                CREATE TABLE IF NOT EXISTS buttons(
                   key integer PRIMARY KEY,
                   uuid text NOT NULL,
                   device text,
                   x integer,
                   y integer,
                   svg text
                );""")
table_cursor.execute("""
                CREATE TABLE IF NOT EXISTS button_states(
                   key integer PRIMARY KEY,
                   state integer,
                   state_update text
                );""")
table_cursor.execute("DELETE FROM button_states;")
database_first.commit()
table_cursor.close()
database_first.close()


def save_button(key: int, button: SDButton):
    """Save button to database."""
    database = sqlite3.connect(DB_FILE)
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
    database.close()


def get_button(key: int) -> any:
    """Get a button from the database."""
    database = sqlite3.connect(DB_FILE)
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
    database.close()
    return button


def get_button_by_uuid(uuid: str) -> any:
    """Get a button from the database."""
    database = sqlite3.connect(DB_FILE)
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
    database.close()
    return button


def get_button_key(uuid: str) -> int:
    """Get a button key from the database."""
    database = sqlite3.connect(DB_FILE)
    cursor = database.cursor()
    result = cursor.execute(f"SELECT key FROM buttons WHERE uuid=\"{uuid}\"")
    matching_buttons = result.fetchall()
    if len(matching_buttons) == 0:
        return -1
    row = matching_buttons[0]
    key = row[0]
    cursor.close()
    database.close()
    return key


def get_buttons() -> dict[str, SDButton]:
    """Load all buttons from the database."""
    result: dict[str, SDButton] = {}
    database = sqlite3.connect(DB_FILE)
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
    database.close()
    print(f"Loaded {len(result)} buttons from DB")
    return result


def write_button_state(key: int, state: bool, update: str):
    """Write button state to database."""
    state_int = 0
    if state is True:
        state_int = 1

    database = sqlite3.connect(DB_FILE)
    cursor = database.cursor()

    # Check if exists
    result = cursor.execute(f"SELECT state FROM button_states WHERE key={key}")
    matching_states = result.fetchall()
    if len(matching_states) > 0:
        # Perform update
        cursor.execute(
            f"UPDATE button_states SET state={state_int}, state_update=\"{update}\" WHERE key={key}")
    else:
        # Create new row
        cursor.execute(
            f"INSERT INTO button_states VALUES ({key}, {state_int}, \"{update}\")")
    database.commit()
    print(f"Saved button_state with key {key} to database")
    cursor.close()
    database.close()


def get_button_state(key: int) -> any:
    """Load button_state from database."""
    result = ()
    database = sqlite3.connect(DB_FILE)
    cursor = database.cursor()
    result = cursor.execute(
        f"SELECT key,state,state_update FROM button_states WHERE key={key}")
    matching_states = result.fetchall()
    if len(matching_states) == 0:
        return None
    row = matching_states[0]
    state = False
    if row[1] == 1:
        state = True
    result = (state, row[2])
    cursor.close()
    database.close()
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
    if not isinstance(button, SDButton):
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
    if not isinstance(button, SDButton):
        return web.Response(status=404, text="Button not found")

    # Update icon
    update_button_icon(uuid, body)

    print("Icon for button", uuid, "changed")

    return web.Response(text="Icon changed")


async def websocket_handler(request: web.Request):
    """Handle websocket."""
    web_socket = web.WebSocketResponse()
    await web_socket.prepare(request)

    await web_socket.send_str(encode({"event": "connected", "args": {}}))

    websocket_connections.append(web_socket)

    async for msg in web_socket:
        if msg.type == aiohttp.WSMsgType.TEXT:
            print(msg.data)
            if msg.data == "close":
                await web_socket.close()
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print(
                f"Websocket connection closed with exception {web_socket.exception()}")

    websocket_connections.remove(web_socket)
    return web_socket


async def websocket_broadcast(message: str):
    """Send a message to each websocket client."""
    print(f"Broadcast to {len(websocket_connections)} clients")
    for connection in websocket_connections:
        await connection.send_str(message)


async def broadcast_status():
    """Broadcast the current status of the streamdeck."""

    # Collect data
    data = {
        "event": "status",
        "args": {
            "devices": devices,
            "application": application,
            "buttons": get_buttons()
        }
    }

    data_str = encode(data, unpicklable=False)
    data_str = (
        data_str.replace('"x_pos"', '"x"')
        .replace('"y_pos"', '"y"')
        .replace('"platform_version"', '"platformVersion"')
    )

    # Broadcast
    await websocket_broadcast(data_str)


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


async def start_server_async(host: str = "0.0.0.0", port: int = PLUGIN_PORT):
    """Start API server."""
    runner = create_runner()
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print("Started Stream Deck API server on port", PLUGIN_PORT)

    Timer(10, broadcast_status)


def get_position(deck: StreamDeck, key: int) -> SDButtonPosition:
    """Get the position of a key."""
    return SDButtonPosition({"x": int(key / deck.KEY_COLS), "y": key % deck.KEY_COLS})


async def long_press_callback(key: int):
    """Handle callback after long press seconds."""
    print("Long press detected")

    # Check state of button
    for deck in streamdecks:
        if not deck.is_visual():
            continue

        if not deck.is_open():
            deck.open()

        states = deck.key_states()

        button = get_button(key)
        if not isinstance(button, SDButton):
            return

        if states[key] is True:
            await websocket_broadcast(encode({"event": "longPress", "args": button.uuid}))


async def on_key_change(_: StreamDeck, key: int, state: bool):
    """Handle key change callbacks."""
    button = get_button(key)
    if not isinstance(button, SDButton):
        return

    if state is True:
        await websocket_broadcast(encode(
            {"event": "keyDown", "args": button.uuid}))
        print("Waiting for button release")
        # Start timer
        Timer(LONG_PRESS_SECONDS, lambda: long_press_callback(key), False)
    else:
        await websocket_broadcast(encode(
            {"event": "keyUp", "args": button.uuid}))

    now = datetime.now()

    db_button_state = get_button_state(key)

    if not isinstance(db_button_state, tuple):
        write_button_state(key, state, now.strftime(DATETIME_FORMAT))
        return

    last_state: bool = db_button_state[0]
    last_update: str = db_button_state[1]
    last_update_datetime = datetime.strptime(last_update, DATETIME_FORMAT)
    diff = now - last_update_datetime

    if last_state is True and state is False and diff.seconds < LONG_PRESS_SECONDS:
        await websocket_broadcast(
            encode({"event": "singleTap", "args": button.uuid}))
        write_button_state(key, state, now.strftime(DATETIME_FORMAT))
        return

    write_button_state(key, state, now.strftime(DATETIME_FORMAT))


def update_button_icon(uuid: str, svg: str):
    """Update a button icon."""
    for deck in streamdecks:
        if not deck.is_visual():
            continue

        if not deck.is_open():
            deck.open()

        button = get_button_by_uuid(uuid)
        button_key = get_button_key(uuid)
        if isinstance(button, SDButton) and button_key >= 0:
            set_icon(deck, button_key, svg)
            button.svg = svg
            save_button(button_key, button)


def set_icon(deck: StreamDeck, key: int, svg: str):
    """Draw an icon to the button."""
    png_bytes = io.BytesIO()
    cairosvg.svg2png(svg.encode("utf-8"), write_to=png_bytes)

    icon = Image.open(png_bytes)
    image = PILHelper.create_scaled_image(deck, icon)

    deck.set_key_image(key, PILHelper.to_native_format(deck, image))


def init_all():
    """Init Stream Deck devices."""
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
            if not isinstance(button, SDButton):
                position = get_position(deck, key)
                new_button = SDButton(
                    {
                        "uuid": hri.get_new_id().lower().replace(" ", "-"),
                        "device": serial,
                        "position": {"x": position.y_pos, "y": position.x_pos},
                        "svg": DEFAULT_ICON,
                    }
                )
                save_button(key, new_button)

        deck.reset()
        # Write svg to buttons
        for key, button in get_buttons().items():
            set_icon(deck, key, button.svg)

        deck.set_key_callback_async(on_key_change)


def get_local_ip():
    """Get local ip address."""
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.connect(('192.255.255.255', 1))
        address = connection.getsockname()[0]
    except socket.error:
        address = '127.0.0.1'
    finally:
        connection.close()
    return address


def start_ssdp_server():
    """Start SSDP server."""
    print("Starting SSDP server ...")

    address = get_local_ip()
    broadcast = "239.255.255.250"
    location = f"http://{address}:{PLUGIN_PORT}/device.xml"
    usn = f"uuid:{str(uuid4())}::{SD_SSDP}"
    server = "python/3 UPnP/1.1 ssdpy/0.4.1"

    print(f"IP Address for SSDP: {address}")
    print(f"SSDP broadcast ip: {broadcast}")
    print(f"SSDP location: {location}")

    server = SSDPServer(usn,    # FIXME socket.setsockopt(): no such device No such device
                        address=broadcast,
                        location=location,
                        max_age=1800,
                        extra_fields={
                            "st": SD_SSDP,
                            "server": server,
                            "deviceType": SD_SSDP,
                        })
    server.serve_forever()


class Timer:
    """Timer class."""

    def __init__(self, interval, callback, repeating=True):
        """Init timer."""
        self._interval = interval
        self._callback = callback
        self._repeating = repeating
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._interval)
        await self._callback()
        if self._repeating:
            self._task = asyncio.ensure_future(self._job())

    def cancel(self):
        """Cancel timer."""
        self._task.cancel()


def start():
    """Entrypoint."""
    init_all()

    # SSDP server
    ssdp_server = Process(target=start_ssdp_server)
    ssdp_server.start()

    # API server
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server_async())
    loop.run_forever()

    ssdp_server.join()
