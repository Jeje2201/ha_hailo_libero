"""Local Hailo Libero API, independent of Home Assistant."""

from .client import HailoClient
from .models import (
    HailoAuthenticationError,
    HailoConnectionError,
    HailoError,
    HailoProtocolError,
    HailoSnapshot,
    RangeSetting,
    parse_page,
)

__all__ = [
    "HailoAuthenticationError",
    "HailoClient",
    "HailoConnectionError",
    "HailoError",
    "HailoProtocolError",
    "HailoSnapshot",
    "RangeSetting",
    "parse_page",
]