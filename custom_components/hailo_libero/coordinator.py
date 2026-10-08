"""Coordinate settings refreshes and connection recovery."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HailoAuthenticationError, HailoClient, HailoError, HailoSnapshot
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HailoCoordinator(DataUpdateCoordinator[HailoSnapshot]):
    """Poll only while entities are subscribed."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HailoClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> HailoSnapshot:
        try:
            return await self.client.async_read()
        except HailoAuthenticationError as err:
            raise ConfigEntryAuthFailed("Device rejected authentication") from err
        except HailoError as err:
            raise UpdateFailed("Unable to read Hailo Libero settings") from err


type HailoConfigEntry = ConfigEntry[HailoCoordinator]