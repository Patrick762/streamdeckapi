import asyncio
import json
from streamdeckapi import SDWebsocketMessage, StreamDeckApi

async def __main__():
    deck = StreamDeckApi("localhost")
    info = await deck.get_info(False)

    if info is None:
        print("Error getting info")
        return

    print(json.dumps(info))

loop = asyncio.get_event_loop()
loop.run_until_complete(__main__())
