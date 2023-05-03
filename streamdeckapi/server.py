"""Stream Deck API Server."""

import aiohttp
import asyncio
from aiohttp import web, WSCloseCode

# from StreamDeck.DeviceManager import DeviceManager
from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT


async def api_info_handler(request: web.Request):
    return web.Response(text="Info")


async def api_icon_get_handler(request: web.Request):
    btnId = request.match_info["btnId"]
    return web.Response(text="Icon get")


async def api_icon_set_handler(request: web.Request):
    btnId = request.match_info["btnId"]
    body = await request.text()
    print(body)
    return web.Response(text="Icon set")


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
