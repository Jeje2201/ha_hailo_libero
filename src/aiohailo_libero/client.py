"""Session-safe asynchronous HTTP client for Hailo Libero 3.0."""

import asyncio
from collections.abc import Mapping
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout

from .models import (
    HailoAuthenticationError,
    HailoConnectionError,
    HailoProtocolError,
    HailoSnapshot,
    parse_page,
)


class HailoClient:
    """Use a supplied session without owning or closing it."""

    def __init__(
        self,
        host: str,
        password: str,
        session: ClientSession,
        *,
        port: int = 81,
        timeout: float = 10,
    ) -> None:
        host = host.strip()
        if not host or any(char in host for char in "/:@?# "):
            raise ValueError("Use an IPv4 address or hostname, without scheme or port")
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port")
        self._base_url = f"http://{host}:{port}"
        self._password = password
        self._session = session
        self._timeout = ClientTimeout(total=timeout)
        self._cookies: dict[str, str] = {}
        self._authenticated = False
        self._lock = asyncio.Lock()

    async def _request(
        self, method: str, path: str, data: Mapping[str, str] | None = None
    ) -> tuple[int, str, str | None]:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                data=data,
                cookies=self._cookies,
                allow_redirects=False,
                timeout=self._timeout,
            ) as response:
                self._cookies.update(
                    {name: cookie.value for name, cookie in response.cookies.items()}
                )
                return (
                    response.status,
                    await response.text(),
                    response.headers.get("Location"),
                )
        except (ClientError, TimeoutError) as err:
            raise HailoConnectionError("Unable to communicate with device") from err

    async def _login(self) -> None:
        self._cookies.clear()
        self._authenticated = False
        status, _, location = await self._request(
            "POST", "/login", {"pin": self._password}
        )
        if status >= 500:
            raise HailoConnectionError("Device failed during authentication")
        if (
            status not in (301, 302, 303)
            or location is None
            or urlsplit(location).path != "/"
        ):
            raise HailoAuthenticationError("Device rejected authentication")
        self._authenticated = True

    async def _authorized_request(
        self, method: str, path: str, data: Mapping[str, str] | None = None
    ) -> str:
        if not self._authenticated:
            await self._login()
        status, body, location = await self._request(method, path, data)
        if status in (401, 403) or (
            status in (301, 302, 303, 307, 308)
            and location is not None
            and urlsplit(location).path == "/login"
        ):
            await self._login()
            status, body, location = await self._request(method, path, data)
        if status in (401, 403) or (
            status in (301, 302, 303, 307, 308)
            and location is not None
            and urlsplit(location).path == "/login"
        ):
            self._authenticated = False
            raise HailoAuthenticationError("Device session is not authorized")
        if status >= 500:
            raise HailoConnectionError("Device returned a server error")
        if status != 200:
            raise HailoProtocolError(f"Unexpected HTTP status: {status}")
        return body

    async def async_read(self) -> HailoSnapshot:
        """Read settings without collecting Wi-Fi credentials."""
        async with self._lock:
            return parse_page(await self._authorized_request("GET", "/"))

    async def async_open(self) -> None:
        """Trigger opening; never retry after ambiguous network errors."""
        async with self._lock:
            body = await self._authorized_request("GET", "/push")
            if body.strip() != "OK":
                raise HailoProtocolError("Device did not acknowledge opening")

    async def async_restart(self) -> None:
        """Restart the controller once."""
        async with self._lock:
            await self._authorized_request("POST", "/restart")
            self._authenticated = False

    async def async_set_value(self, name: str, value: int) -> HailoSnapshot:
        """Read-modify-write all sliders to preserve the other settings."""
        if name not in ("led", "pwr", "dist"):
            raise ValueError("Unknown setting")
        async with self._lock:
            current = parse_page(await self._authorized_request("GET", "/"))
            setting = getattr(current, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("Setting must be an integer")
            if not setting.minimum <= value <= setting.maximum:
                raise ValueError("Setting is outside the device range")
            data = {
                key: str(value if key == name else getattr(current, key).value)
                for key in ("led", "pwr", "dist")
            }
            await self._authorized_request("POST", "/settings", data)
            return parse_page(await self._authorized_request("GET", "/"))