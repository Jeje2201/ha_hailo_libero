"""Typed device data and protocol errors."""

from dataclasses import dataclass

from bs4 import BeautifulSoup


class HailoError(Exception):
    """Base error for the device API."""


class HailoAuthenticationError(HailoError):
    """The device rejected authentication."""


class HailoConnectionError(HailoError):
    """The device could not be reached."""


class HailoProtocolError(HailoError):
    """The device returned an unsupported response."""


@dataclass(frozen=True, slots=True)
class RangeSetting:
    """A device-provided slider value and its limits."""

    value: int
    minimum: int
    maximum: int


@dataclass(frozen=True, slots=True)
class HailoSnapshot:
    """Only non-sensitive device information and actuator settings."""

    device_id: str
    firmware: str
    status: str
    led: RangeSetting
    pwr: RangeSetting
    dist: RangeSetting


def parse_page(html: str) -> HailoSnapshot:
    """Parse the web UI layout documented by the upstream implementation."""
    soup = BeautifulSoup(html, "html.parser")
    settings: dict[str, RangeSetting] = {}
    try:
        for name in ("led", "pwr", "dist"):
            element = soup.find("input", attrs={"name": name, "type": "range"})
            if element is None:
                raise HailoProtocolError(f"Missing setting: {name}")
            setting = RangeSetting(
                value=int(str(element["value"])),
                minimum=int(str(element["min"])),
                maximum=int(str(element["max"])),
            )
            if not setting.minimum <= setting.value <= setting.maximum:
                raise HailoProtocolError(f"Invalid setting range: {name}")
            settings[name] = setting
        paragraph = soup.find("p")
        if paragraph is None:
            raise HailoProtocolError("Missing device information")
        spans = paragraph.find_all("span")
        if len(spans) < 3:
            raise HailoProtocolError("Incomplete device information")
        values = [str(span.next_sibling or "").strip() for span in spans[:3]]
        if not all(values):
            raise HailoProtocolError("Empty device information")
        return HailoSnapshot(
            device_id=values[0],
            firmware=values[1],
            status=values[2],
            led=settings["led"],
            pwr=settings["pwr"],
            dist=settings["dist"],
        )
    except (KeyError, ValueError, TypeError) as err:
        raise HailoProtocolError("Invalid device page") from err