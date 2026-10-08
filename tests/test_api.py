"""Exercise the actual HTTP client against a simulated local device."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from aiohailo_libero import (
    HailoAuthenticationError,
    HailoClient,
    HailoProtocolError,
    parse_page,
)
from aiohttp import ClientSession, DummyCookieJar, web


def device_page(values: dict[str, int] | None = None) -> str:
    values = values or {"led": 50, "pwr": 70, "dist": 30}
    sliders = "".join(
        f'<input type="range" name="{name}" value="{value}" min="0" max="100">'
        for name, value in values.items()
    )
    return (
        "<html><p><span>Device:</span> LIBERO-123<br>"
        "<span>Firmware:</span> 3.0<br><span>Status:</span> Connected<br></p>"
        f'{sliders}<input name="key" value="WIFI-SECRET"></html>'
    )


@pytest_asyncio.fixture
async def device(unused_tcp_port: int) -> AsyncIterator[tuple[HailoClient, dict]]:
    state = {
        "values": {"led": 50, "pwr": 70, "dist": 30},
        "logins": 0,
        "opens": 0,
        "restarts": 0,
        "writes": 0,
        "expired": False,
        "bad_ack": False,
        "reject": False,
    }

    async def login(request: web.Request) -> web.Response:
        state["logins"] += 1
        data = await request.post()
        if data["pin"] != "custom-password" or state["reject"]:
            return web.Response(text="Invalid PIN")
        state["expired"] = False
        response = web.Response(status=301, headers={"Location": "/"})
        response.set_cookie("session", "valid")
        return response

    async def handle(request: web.Request) -> web.Response:
        if request.cookies.get("session") != "valid" or state["expired"]:
            return web.Response(status=301, headers={"Location": "/login"})
        if request.path == "/push":
            state["opens"] += 1
            return web.Response(text="NO" if state["bad_ack"] else "OK")
        if request.path == "/restart":
            state["restarts"] += 1
            return web.Response(text="OK")
        if request.path == "/settings":
            state["writes"] += 1
            state["values"] = {
                name: int(value) for name, value in (await request.post()).items()
            }
            return web.Response(text="OK")
        return web.Response(text=device_page(state["values"]))

    app = web.Application()
    app.router.add_post("/login", login)
    app.router.add_route("*", "/{path:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    try:
        async with ClientSession(cookie_jar=DummyCookieJar()) as session:
            yield (
                HailoClient(
                    "127.0.0.1", "custom-password", session, port=unused_tcp_port
                ),
                state,
            )
            assert not session.closed
    finally:
        await runner.cleanup()


def test_parse_only_non_sensitive_data() -> None:
    snapshot = parse_page(device_page())
    assert snapshot.device_id == "LIBERO-123"
    assert snapshot.firmware == "3.0"
    assert snapshot.led.value == 50
    assert "SECRET" not in repr(snapshot)


@pytest.mark.parametrize(
    "html",
    ["", "<p>Unknown firmware</p>", device_page().replace('value="50"', 'value="999"')],
)
def test_reject_malformed_page(html: str) -> None:
    with pytest.raises(HailoProtocolError):
        parse_page(html)


async def test_authentication_cookie_and_session_reuse(device: tuple) -> None:
    client, state = device
    assert (await client.async_read()).device_id == "LIBERO-123"
    await client.async_read()
    assert state["logins"] == 1


async def test_session_expiration(device: tuple) -> None:
    client, state = device
    await client.async_read()
    state["expired"] = True
    await client.async_open()
    assert state["logins"] == 2
    assert state["opens"] == 1


async def test_rejected_password(device: tuple) -> None:
    client, state = device
    state["reject"] = True
    with pytest.raises(HailoAuthenticationError):
        await client.async_read()
    assert state["opens"] == 0


async def test_preserve_other_settings(device: tuple) -> None:
    client, state = device
    result = await client.async_set_value("dist", 0)
    assert state["values"] == {"led": 50, "pwr": 70, "dist": 0}
    assert result.dist.value == 0


@pytest.mark.parametrize("value", [-1, 101, 1.5, True])
async def test_invalid_value_never_written(device: tuple, value: int) -> None:
    client, state = device
    with pytest.raises(ValueError):
        await client.async_set_value("led", value)
    assert state["writes"] == 0


async def test_restart_requires_new_login(device: tuple) -> None:
    client, state = device
    await client.async_restart()
    await client.async_read()
    assert state["restarts"] == 1
    assert state["logins"] == 2


async def test_open_requires_acknowledgement(device: tuple) -> None:
    client, state = device
    state["bad_ack"] = True
    with pytest.raises(HailoProtocolError):
        await client.async_open()
    assert state["opens"] == 1