"""Shared device identity and coordinator availability."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HailoCoordinator


class HailoEntity(CoordinatorEntity[HailoCoordinator]):
    """Represent an entity belonging to one Hailo controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HailoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        snapshot = coordinator.data
        self._attr_unique_id = f"{snapshot.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, snapshot.device_id)},
            manufacturer="Hailo",
            model="Libero 3.0",
            name=f"Hailo Libero {snapshot.device_id}",
            sw_version=snapshot.firmware,
        )