"""Read device identity and firmware without issuing actuator commands."""

import argparse
import asyncio
import json
from dataclasses import asdict
from getpass import getpass

from aiohttp import ClientSession, DummyCookieJar

from aiohailo_libero import HailoClient, HailoError


async def probe(host: str, port: int, password: str) -> None:
    async with ClientSession(cookie_jar=DummyCookieJar()) as session:
        snapshot = await HailoClient(host, password, session, port=port).async_read()
    print(json.dumps(asdict(snapshot), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=81)
    arguments = parser.parse_args()
    password = getpass("Device password (not displayed): ")
    try:
        asyncio.run(probe(arguments.host, arguments.port, password))
    except (HailoError, ValueError) as err:
        parser.exit(1, f"{err}\n")