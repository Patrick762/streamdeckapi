"""Stream Deck API."""

import asyncio
from typing import Callable
import json
import logging

import requests
from websockets.client import connect
from websockets.exceptions import WebSocketException

from streamdeckapi.const import PLUGIN_ICON, PLUGIN_INFO, PLUGIN_PORT

from .types import SDInfo, SDWebsocketMessage

_LOGGER = logging.getLogger(__name__)


class StreamDeckApi:
    """Stream Deck API Class."""

    def __init__(
        self,
        host: str,
        on_button_press: any = None,
        on_button_release: any = None,
        on_status_update: any = None,
        on_ws_message: any = None,
        on_ws_connect: any = None,
    ) -> None:
        """Init Stream Deck API object.

        Args:
            on_button_press (Callable[[str], None] or None): Callback if button pressed
            on_button_release (Callable[[str], None] or None): Callback if button released
            on_status_update (Callable[[SDInfo], None] or None): Callback if status update received
            on_ws_message (Callable[[SDWebsocketMessage], None] or None): Callback if websocket message received
            on_ws_connect (Callable[[], None] or None): Callback on websocket connected
        """

        # Type checks
        if on_button_press is not None and not isinstance(
            on_button_press, Callable[[str], None]
        ):
            raise TypeError()
        if on_button_release is not None and not isinstance(
            on_button_release, Callable[[str], None]
        ):
            raise TypeError()
        if on_status_update is not None and not isinstance(
            on_status_update, Callable[[SDInfo], None]
        ):
            raise TypeError()
        if on_ws_message is not None and not isinstance(
            on_ws_message, Callable[[SDWebsocketMessage], None]
        ):
            raise TypeError()
        if on_ws_connect is not None and not isinstance(
            on_ws_connect, Callable[[], None]
        ):
            raise TypeError()

        self._host = host
        self._on_button_press = on_button_press
        self._on_button_release = on_button_release
        self._on_status_update = on_status_update
        self._on_ws_message = on_ws_message
        self._on_ws_connect = on_ws_connect
        self._loop = asyncio.get_event_loop()
        self._running = False
        self._task: any = None

    #
    #   Properties
    #

    @property
    def host(self) -> str:
        """Stream Deck API host."""
        return self._host

    @property
    def _info_url(self) -> str:
        """URL to info endpoint."""
        return f"http://{self._host}:{PLUGIN_PORT}{PLUGIN_INFO}"

    @property
    def _icon_url(self) -> str:
        """URL to icon endpoint."""
        return f"http://{self._host}:{PLUGIN_PORT}{PLUGIN_ICON}/"

    @property
    def _websocket_url(self) -> str:
        """URL to websocket."""
        return f"ws://{self._host}:{PLUGIN_PORT}"

    #
    #   API Methods
    #

    @staticmethod
    def _get_request(url: str) -> any:
        """Handle GET requests.

        Returns:
            requests.Response or None
        """

        try:
            res = requests.get(url, timeout=5)
        except requests.RequestException:
            _LOGGER.debug(
                "Error retrieving data from Stream Deck Plugin (exception). Is it offline?"
            )
            return None
        if res.status_code != 200:
            _LOGGER.debug(
                "Error retrieving data from Stream Deck Plugin (response code). Is it offline?"
            )
            return None
        return res

    @staticmethod
    def _post_request(url: str, data: str, headers) -> any:
        """Handle POST requests.
        
        Returns:
            requests.Response or None
        """

        try:
            res = requests.post(url, data, headers=headers, timeout=5)
        except requests.RequestException:
            _LOGGER.debug("Error sending data to Stream Deck Plugin (exception)")
            return None
        if res.status_code != 200:
            _LOGGER.debug(
                "Error sending data to Stream Deck Plugin (%s). Is the button currently visible?",
                res.reason,
            )
            return None
        return res

    async def get_info(self, in_executor: bool = True) -> any:
        """Get info about Stream Deck.
        
        Returns:
            SDInfo or None
        """

        res: any = None
        if in_executor:
            res = await self._loop.run_in_executor(
                None, self._get_request, self._info_url
            )
        else:
            res = self._get_request(self._info_url)
        if res is None or res.status_code != 200:
            return None
        try:
            rjson = res.json()
        except requests.JSONDecodeError:
            _LOGGER.debug("Error decoding response from %s", self._info_url)
            return None
        try:
            info = SDInfo(rjson)
        except KeyError:
            _LOGGER.debug("Error parsing response from %s to SDInfo", self._info_url)
            return None
        return info

    async def get_icon(self, btn: str) -> any:
        """Get svg icon from Stream Deck button.
        
        Returns:
            str or None
        """

        url = f"{self._icon_url}{btn}"
        res = await self._loop.run_in_executor(None, self._get_request, url)
        if res is None or res.status_code != 200:
            return None
        if res.headers.get("Content-Type", "") != "image/svg+xml":
            _LOGGER.debug("Invalid content type received from %s", url)
            return None
        return res.text

    async def update_icon(self, btn: str, svg: str) -> bool:
        """Update svg icon of Stream Deck button."""
        url = f"{self._icon_url}{btn}"
        res = await self._loop.run_in_executor(
            None,
            self._post_request,
            url,
            svg.encode("utf-8"),
            {"Content-Type": "image/svg+xml"},
        )
        return isinstance(res, requests.Response) and res.status_code == 200

    #
    #   Websocket Methods
    #

    def _on_button_change(self, uuid: any, state: bool):
        """Handle button down event.
        
        Args:
            uuid (str or dict): UUID of the button
            state (bool): State of the button
        """

        if not isinstance(uuid, str):
            _LOGGER.debug("Method _on_button_change: uuid is not str")
            return
        if state is True and self._on_button_press is not None:
            self._on_button_press(uuid)
        elif state is False and self._on_button_release is not None:
            self._on_button_release(uuid)

    def _on_ws_status_update(self, info: any):
        """Handle Stream Deck status update event.
        
        Args:
            info (SDInfo or str or dict): Stream Deck Info
        """

        if not isinstance(info, SDInfo):
            _LOGGER.debug("Method _on_ws_status_update: info is not SDInfo")
            return
        if self._on_status_update is not None:
            self._on_status_update(info)

    def _on_message(self, msg: str):
        """Handle websocket messages."""
        if not isinstance(msg, str):
            return

        _LOGGER.debug(msg)

        try:
            datajson = json.loads(msg)
        except json.JSONDecodeError:
            _LOGGER.debug("Method _on_message: Websocket message couldn't get parsed")
            return
        try:
            data = SDWebsocketMessage(datajson)
        except KeyError:
            _LOGGER.debug(
                "Method _on_message: Websocket message couldn't get parsed to SDWebsocketMessage"
            )
            return

        _LOGGER.debug("Method _on_message: Got event %s", data.event)

        if self._on_ws_message is not None:
            self._on_ws_message(data)

        if data.event == "keyDown":
            self._on_button_change(data.args, True)
        elif data.event == "keyUp":
            self._on_button_change(data.args, False)
        elif data.event == "status":
            self._on_ws_status_update(data.args)
        else:
            _LOGGER.debug(
                "Method _on_message: Unknown event from Stream Deck Plugin received (Event: %s)",
                data.event,
            )

    async def _websocket_loop(self):
        """Start the websocket client loop."""
        self._running = True
        while self._running:
            info = await self.get_info()
            if isinstance(info, SDInfo):
                _LOGGER.debug("Method _websocket_loop: Streamdeck online")
                try:
                    async with connect(self._websocket_url) as websocket:
                        if self._on_ws_connect is not None:
                            self._on_ws_connect()
                        try:
                            while self._running:
                                data = await asyncio.wait_for(
                                    websocket.recv(), timeout=60
                                )
                                self._on_message(data)
                            await websocket.close()
                            _LOGGER.debug("Method _websocket_loop: Websocket closed")
                        except WebSocketException:
                            _LOGGER.debug(
                                "Method _websocket_loop: Websocket client crashed. Restarting it"
                            )
                        except asyncio.TimeoutError:
                            _LOGGER.debug(
                                "Method _websocket_loop: Websocket client timed out. Restarting it"
                            )
                except WebSocketException:
                    _LOGGER.debug(
                        "Method _websocket_loop: Websocket client not connecting. Restarting it"
                    )

    def start_websocket_loop(self):
        """Start the websocket client."""
        self._task = asyncio.create_task(self._websocket_loop())

    def stop_websocket_loop(self):
        """Stop the websocket client."""
        self._running = False
