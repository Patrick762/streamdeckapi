"""Stream Deck API types."""


class SDApplication:
    """Stream Deck Application Type."""

    font: str
    language: str
    platform: str
    platform_version: str
    version: str

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Application object."""
        self.font = obj["font"]
        self.language = obj["language"]
        self.platform = obj["platform"]
        self.platform_version = obj["platformVersion"]
        self.version = obj["version"]


class SDSize:
    """Stream Deck Size Type."""

    columns: int
    rows: int

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Size object."""
        self.columns = obj["columns"]
        self.rows = obj["rows"]


class SDDevice:
    """Stream Deck Device Type."""

    id: str
    name: str
    type: int
    size: SDSize

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Device object."""
        self.id = obj["id"]
        self.name = obj["name"]
        self.type = obj["type"]
        self.size = SDSize(obj["size"])


class SDButtonPosition:
    """Stream Deck Button Position Type."""

    x_pos: int
    y_pos: int

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Button Position object."""
        self.x_pos = obj["x"]
        self.y_pos = obj["y"]


class SDButton:
    """Stream Deck Button Type."""

    uuid: str
    device: str
    position: SDButtonPosition
    svg: str

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Button object."""
        self.uuid = obj["uuid"]
        self.device = obj["device"]
        self.svg = obj["svg"]
        self.position = SDButtonPosition(obj["position"])


class SDInfo(dict):
    """Stream Deck Info Type."""

    application: SDApplication
    devices: list[SDDevice] = []
    buttons: dict[str, SDButton] = {}

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Info object."""
        dict.__init__(self, obj)
        self.application = SDApplication(obj["application"])
        for device in obj["devices"]:
            self.devices.append(SDDevice(device))
        for _id in obj["buttons"]:
            self.buttons.update({_id: SDButton(obj["buttons"][_id])})


class SDWebsocketMessage:
    """Stream Deck Websocket Message Type."""

    event: str
    args: SDInfo | str | dict

    def __init__(self, obj: dict) -> None:
        """Init Stream Deck Websocket Message object."""
        self.event = obj["event"]
        if obj["args"] == {}:
            self.args = {}
            return
        if isinstance(obj["args"], str):
            self.args = obj["args"]
            return
        self.args = SDInfo(obj["args"])
