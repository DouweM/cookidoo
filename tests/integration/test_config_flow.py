"""Tests for the Cookidoo config and reauth flows."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cookidoo.const import (
    CONF_EMAIL,
    CONF_MARKET,
    CONF_PASSWORD,
    DOMAIN,
)
from custom_components.cookidoo.cookidoo import CookidooAuthError, CookidooError

USER_INPUT = {
    CONF_EMAIL: "me@example.com",
    CONF_PASSWORD: "pw",
    CONF_MARKET: "mx",
}


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A valid login creates the entry with the account's dcid as unique id."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "custom_components.cookidoo.config_flow.CookidooClient",
            return_value=mock_client,
        ),
        patch(
            "custom_components.cookidoo.coordinator.CookidooClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "me@example.com"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "user-uuid"


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A rejected login surfaces the ``invalid_auth`` error, then recovers."""
    mock_client.login.side_effect = CookidooAuthError("bad creds")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.cookidoo.config_flow.CookidooClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover: clear the error and complete the flow.
    mock_client.login.side_effect = None
    with (
        patch(
            "custom_components.cookidoo.config_flow.CookidooClient",
            return_value=mock_client,
        ),
        patch(
            "custom_components.cookidoo.coordinator.CookidooClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A connection failure surfaces the ``cannot_connect`` error."""
    mock_client.login.side_effect = CookidooError("boom")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.cookidoo.config_flow.CookidooClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_single_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A second config flow aborts because only one entry is allowed."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Reauth revalidates and updates the stored password."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "custom_components.cookidoo.config_flow.CookidooClient",
            return_value=mock_client,
        ),
        patch(
            "custom_components.cookidoo.coordinator.CookidooClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new-pw"})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-pw"
