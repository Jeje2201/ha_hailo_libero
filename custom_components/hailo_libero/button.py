"""Open and restart the controller."""

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import HailoAuthenticationError, HailoConnectionError, HailoError
from .const import DOMAIN
from .coordinator import HailoConfigEntry, HailoCoordinator
from .entity import HailoEntity

PARALLEL_UPDATES = 1

BUTTONS = (
    ButtonEntityDescription(key="open", translation_key="open"),
    ButtonEntityDescription(
        key="restart",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HailoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        HailoButton(entry.runtime_data, description) for description in BUTTONS
    )


class HailoButton(HailoEntity, ButtonEntity):
    """An acknowledged, momentary operation, not a presumed lid state."""

    def __init__(
        self, coordinator: HailoCoordinator, description: ButtonEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            if self.entity_description.key == "open":
                await self.coordinator.client.async_open()
            else:
                await self.coordinator.client.async_restart()
        except HailoAuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except HailoConnectionError as err:
            self.coordinator.async_set_update_error(
                UpdateFailed("Unable to communicate with Hailo Libero")
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        except HailoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()