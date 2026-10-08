"""UI setup, reauthentication and address changes."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    HailoAuthenticationError,
    HailoClient,
    HailoConnectionError,
    HailoProtocolError,
    HailoSnapshot,
)
from .const import DEFAULT_PORT, DOMAIN


class HailoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate the real device before storing configuration."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> HailoSnapshot:
        client = HailoClient(
            data[CONF_HOST],
            data[CONF_PASSWORD],
            async_get_clientsession(self.hass),
            port=data[CONF_PORT],
        )
        return await client.async_read()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("user", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("reauth_confirm", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("reconfigure", user_input)

    async def _async_form(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        existing = None
        if step_id == "reauth_confirm":
            existing = self._get_reauth_entry()
        elif step_id == "reconfigure":
            existing = self._get_reconfigure_entry()
        defaults = dict(existing.data) if existing else {}
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**defaults, **user_input}
            data.setdefault(CONF_PORT, DEFAULT_PORT)
            data[CONF_HOST] = data[CONF_HOST].strip()
            try:
                snapshot = await self._validate(data)
            except HailoAuthenticationError:
                errors["base"] = "invalid_auth"
            except HailoConnectionError:
                errors["base"] = "cannot_connect"
            except HailoProtocolError:
                errors["base"] = "unsupported_response"
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(snapshot.device_id)
                if existing is not None:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        existing, data_updates=data
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Hailo Libero {snapshot.device_id}", data=data
                )
            defaults.update(user_input)
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id=step_id, data_schema=schema, errors=errors
        )