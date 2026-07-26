"""Config and options flow for the Cookidoo integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_MARKET,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .cookidoo import (
    CookidooAuthError,
    CookidooClient,
    CookidooError,
    all_markets,
    get_market,
)

_MARKET_OPTIONS = [
    SelectOptionDict(value=m.market_code, label=f"{m.name} ({m.main_domain})")
    for m in sorted(all_markets(), key=lambda m: m.name)
]

_EMAIL = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_MARKET = SelectSelector(SelectSelectorConfig(options=_MARKET_OPTIONS, mode=SelectSelectorMode.DROPDOWN))


async def _validate(hass: Any, email: str, password: str, market: str) -> str:
    """Log in and return the account's stable id. Raises on failure."""
    client = CookidooClient(email, password, market=market, http=get_async_client(hass))
    await client.login()
    user = await client.get_user_info()
    return (user.dcid if user and user.dcid else email).lower()


class CookidooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Cookidoo config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect credentials + market and validate them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id = await _validate(
                    self.hass,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_MARKET],
                )
            except CookidooAuthError:
                errors["base"] = "invalid_auth"
            except CookidooError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): _EMAIL,
                    vol.Required(CONF_PASSWORD): _PASSWORD,
                    vol.Required(CONF_MARKET, default="xp"): _MARKET,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauth when the stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Re-collect the password for the existing account."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _validate(
                    self.hass,
                    reauth_entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    reauth_entry.data[CONF_MARKET],
                )
            except CookidooAuthError:
                errors["base"] = "invalid_auth"
            except CookidooError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD}),
            description_placeholders={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> CookidooOptionsFlow:
        """Return the options flow."""
        return CookidooOptionsFlow()


class CookidooOptionsFlow(OptionsFlow):
    """Tune language and poll interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        market = get_market(self.config_entry.data[CONF_MARKET])
        lang_options = [SelectOptionDict(value=lang, label=lang) for lang in market.allowed_languages] or [
            SelectOptionDict(value=market.default_language, label=market.default_language)
        ]
        current_lang = self.config_entry.options.get(CONF_LANGUAGE, market.default_language)
        current_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds()))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LANGUAGE, default=current_lang): SelectSelector(
                        SelectSelectorConfig(options=lang_options, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Required(CONF_SCAN_INTERVAL, default=current_interval): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=10,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
