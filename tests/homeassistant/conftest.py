"""Fixtures for integration tests; Linux Home Assistant runtime required."""

from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

from custom_components.hailo_libero.api import HailoSnapshot, RangeSetting


@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations):
    """Allow the test loader to load this project's integration."""


@pytest.fixture
def mock_client():
    snapshot = HailoSnapshot(
        device_id="LIBERO-123",
        firmware="3.0",
        status="Connected",
        led=RangeSetting(50, 0, 100),
        pwr=RangeSetting(70, 0, 100),
        dist=RangeSetting(30, 0, 100),
    )
    with patch(
        "custom_components.hailo_libero.config_flow.HailoClient", autospec=True
    ) as flow_factory:
        client = flow_factory.return_value
        client.async_read.return_value = snapshot
        client.async_set_value.return_value = snapshot
        with patch(
            "custom_components.hailo_libero.HailoClient", return_value=client
        ) as setup_factory:
            yield client, flow_factory, setup_factory