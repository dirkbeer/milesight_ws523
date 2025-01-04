"""Config flow for Milesight WS523 integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_DEVICE_EUI, CONF_QOS, DEFAULT_QOS

class WS523ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Milesight WS523."""

    VERSION = 1

    def _validate_eui(self, eui: str) -> bool:
        """Validate EUI format."""
        try:
            # EUI should be 16 hex characters
            return len(eui) == 16 and all(c in '0123456789ABCDEFabcdef' for c in eui)
        except ValueError:
            return False

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            device_eui = user_input[CONF_DEVICE_EUI]
            
            if not self._validate_eui(device_eui):
                errors[CONF_DEVICE_EUI] = "invalid_device_eui"
            
            if not errors:
                await self.async_set_unique_id(device_eui)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"WS523 {device_eui[-4:]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_EUI): str,
                    vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
                        vol.Coerce(int), vol.In([0, 1, 2])
                    ),
                }
            ),
            errors=errors,
        )