"""Stream Deck API Server."""

import aiohttp
import asyncio
import platform
from jsonpickle import encode
from aiohttp import web

# from StreamDeck.DeviceManager import DeviceManager
from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT
from streamdeckapi.types import SDApplication, SDButton, SDDevice

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
devices.append(
    SDDevice(
        {
            "id": "08B602C026FC8D1989FDF80EB8658612",
            "name": "Stream Deck",
            "size": {"columns": 5, "rows": 3},
            "type": 0,
        }
    )
)
buttons["547686796543735"] = SDButton(
    {
        "uuid": "kind-sloth-97",
        "device": "08B602C026FC8D1989FDF80EB8658612",
        "position": {"x": 0, "y": 0},
        "svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72"><rect width="72" height="72" fill="#000" /><text text-anchor="middle" x="35" y="15" fill="#fff" font-size="12">off</text><text text-anchor="middle" x="35" y="65" fill="#fff" font-size="12">Philips Hue Huelight</text><g transform="translate(16, 12) scale(0.5)"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -512 512 512"><path fill="#e00" d="M256 -405Q215 -405 181 -385Q147 -365 127 -331Q107 -297 107 -256Q107 -219 124 -186.5Q141 -154 171 -134V-85Q171 -76 177 -70Q183 -64 192 -64H320Q329 -64 335 -70Q341 -76 341 -85V-134Q371 -154 388 -186.5Q405 -219 405 -256Q405 -297 385 -331Q365 -365 331 -385Q297 -405 256 -405ZM192 0Q192 9 198 15Q204 21 213 21H299Q308 21 314 15Q320 9 320 0V-21H192Z"/></svg></g></svg>',
    }
)


async def api_info_handler(request: web.Request):
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


def start():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server())
    loop.run_forever()
