"""Stream Deck API Tools."""

from .types import SDInfo


def get_model(info: SDInfo) -> str:
    """Get Stream Deck model."""
    if len(info.devices) == 0:
        return "None"
    size = info.devices[0].size
    if size.columns == 3 and size.rows == 2:
        return "Stream Deck Mini"
    if size.columns == 5 and size.rows == 3:
        return "Stream Deck MK.2"
    if size.columns == 4 and size.rows == 2:
        return "Stream Deck +"
    if size.columns == 8 and size.rows == 4:
        return "Stream Deck XL"
    return "Unknown"
