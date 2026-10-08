"""Set up the local Hailo Libero integration."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HailoClient
from .const import DEFAULT_PORT
from .coordinator import HailoConfigEntry, HailoCoordinator

PLATFORMS = [Platform.BUTTON, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: HailoConfigEntry) -> bool:
    """Validate access before creating entities."""
    client = HailoClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    coordinator = HailoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HailoConfigEntry) -> bool:
    """Unload entities; the HTTP session belongs to Home Assistant."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)