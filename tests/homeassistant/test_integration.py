"""Test UI configuration, lifecycle, coordinator and entity operations."""

from dataclasses import replace
from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hailo_libero.api import (
    HailoAuthenticationError,
    HailoConnectionError,
    HailoProtocolError,
)
from custom_components.hailo_libero.const import DOMAIN

DATA = {CONF_HOST: "192.168.1.50", CONF_PORT: 81, CONF_PASSWORD: "custom-password"}


def make_entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Hailo Libero LIBERO-123",
        unique_id="LIBERO-123",
        data=DATA,
    )
    entry.add_to_hass(hass)
    return entry


async def test_user_flow(hass, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA
    assert result["result"].unique_id == "LIBERO-123"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (HailoAuthenticationError(), "invalid_auth"),
        (HailoConnectionError(), "cannot_connect"),
        (HailoProtocolError(), "unsupported_response"),
        (ValueError(), "invalid_host"),
    ],
)
async def test_flow_errors(hass, mock_client, error, expected) -> None:
    mock_client[0].async_read.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_duplicate(hass, mock_client) -> None:
    make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("source", ["user", "reauth", "reconfigure"])
@pytest.mark.parametrize(
    "error",
    [
        HailoAuthenticationError(),
        HailoConnectionError(),
        HailoProtocolError(),
        ValueError(),
    ],
)
async def test_flow_recovers_in_same_flow(hass, mock_client, source, error) -> None:
    entry = make_entry(hass) if source != "user" else None
    context = {"source": source}
    if entry is not None:
        context["entry_id"] = entry.entry_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context=context, data=entry.data if source == "reauth" else None
    )
    flow_id = result["flow_id"]
    mock_client[0].async_read.side_effect = error
    result = await hass.config_entries.flow.async_configure(flow_id, DATA)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]
    assert result["flow_id"] == flow_id
    mock_client[0].async_read.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, DATA)
    await hass.async_block_till_done()
    if source == "user":
        assert result["type"] is FlowResultType.CREATE_ENTRY
    else:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == f"{source}_successful"


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
async def test_update_rejects_different_device(hass, mock_client, source) -> None:
    entry = make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=entry.data if source == "reauth" else None,
    )
    mock_client[0].async_read.return_value = replace(
        mock_client[0].async_read.return_value, device_id="OTHER-CONTROLLER"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DATA, CONF_HOST: "192.168.1.99"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == DATA
    assert entry.unique_id == "LIBERO-123"


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
async def test_update_existing_entry(hass, mock_client, source) -> None:
    entry = make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=entry.data if source == "reauth" else None,
    )
    assert result["type"] is FlowResultType.FORM
    new_data = {**DATA, CONF_PASSWORD: "new-password"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new_data)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == f"{source}_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"


async def test_setup_entities_password_and_unload(hass, mock_client) -> None:
    entry = make_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert mock_client[2].call_args.args[1] == "custom-password"
    assert len(hass.states.async_all("number")) == 3
    assert len(hass.states.async_all("button")) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_offline_setup_is_retried(hass, mock_client) -> None:
    mock_client[0].async_read.side_effect = HailoConnectionError()
    entry = make_entry(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_authentication_failure_requests_reauth(hass, mock_client) -> None:
    mock_client[0].async_read.side_effect = HailoAuthenticationError()
    entry = make_entry(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_open_button(hass, mock_client) -> None:
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity = hass.states.async_all("button")[0]
    await hass.services.async_call(
        "button", "press", {"entity_id": entity.entity_id}, blocking=True
    )
    mock_client[0].async_open.assert_awaited_once()


@pytest.mark.parametrize("domain", ["number", "button"])
@pytest.mark.parametrize(
    ("error", "unavailable"),
    [(HailoConnectionError(), True), (HailoProtocolError(), False)],
)
async def test_command_error_updates_availability(
    hass, mock_client, domain, error, unavailable
) -> None:
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_client[0].async_set_value.side_effect = error
    mock_client[0].async_open.side_effect = error
    entity = hass.states.async_all(domain)[0]
    data = {"entity_id": entity.entity_id}
    if domain == "number":
        data["value"] = 42
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            domain,
            "set_value" if domain == "number" else "press",
            data,
            blocking=True,
        )
    await hass.async_block_till_done()
    for state in hass.states.async_all("number") + hass.states.async_all("button"):
        assert (state.state == STATE_UNAVAILABLE) is unavailable
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    for state in hass.states.async_all("number") + hass.states.async_all("button"):
        assert state.state != STATE_UNAVAILABLE


async def test_periodic_polling_detects_disconnect_and_recovery(
    hass, mock_client, freezer
) -> None:
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_client[0].async_read.side_effect = HailoConnectionError()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    for state in hass.states.async_all("number") + hass.states.async_all("button"):
        assert state.state == STATE_UNAVAILABLE
    mock_client[0].async_read.side_effect = None
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    for state in hass.states.async_all("number") + hass.states.async_all("button"):
        assert state.state != STATE_UNAVAILABLE
