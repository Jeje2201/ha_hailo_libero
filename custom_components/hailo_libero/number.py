"""Expose only the ranges advertised by the device."""

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import (
    HailoAuthenticationError,
    HailoConnectionError,
    HailoError,
    RangeSetting,
)
from .const import DOMAIN
from .coordinator import HailoConfigEntry, HailoCoordinator
from .entity import HailoEntity

PARALLEL_UPDATES = 1

NUMBERS = tuple(
    NumberEntityDescription(
        key=key,
        translation_key=key,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.SLIDER,
        native_step=1,
    )
    for key in ("led", "pwr", "dist")
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HailoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        HailoNumber(entry.runtime_data, description) for description in NUMBERS
    )


class HailoNumber(HailoEntity, NumberEntity):
    """A device setting with bounds supplied by its firmware."""

    def __init__(
        self, coordinator: HailoCoordinator, description: NumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def _setting(self) -> RangeSetting:
        return getattr(self.coordinator.data, self.entity_description.key)

    @property
    def native_value(self) -> float:
        return self._setting.value

    @property
    def native_min_value(self) -> float:
        return self._setting.minimum

    @property
    def native_max_value(self) -> float:
        return self._setting.maximum

    async def async_set_native_value(self, value: float) -> None:
        if not float(value).is_integer():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_value"
            )
        try:
            snapshot = await self.coordinator.client.async_set_value(
                self.entity_description.key, int(value)
            )
        except HailoAuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_value"
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
        self.coordinator.async_set_updated_data(snapshot)