import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ShellyAuthError, ShellyRpcClient, get_shelly_credentials

DOMAIN = "shelly_plug_led"

class ShellyPlugLedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelly Plug LED Ring with device & area filtering."""

    VERSION = 2

    def __init__(self):
        self._reauth_entry = None

    async def async_step_user(self, user_input=None):
        """Handle the initial user setup step."""
        errors = {}
        dev_reg = dr.async_get(self.hass)
        area_reg = ar.async_get(self.hass)
        
        # Track hosts that have already been set up in this integration
        configured_hosts = {
            entry.data.get("host") for entry in self._async_current_entries()
        }
        
        # Pull all active configuration entries matching the official Shelly domain
        shelly_entries = self.hass.config_entries.async_entries("shelly")
        
        devices = {}
        for entry in shelly_entries:
            host = entry.data.get("host") or entry.data.get("ip")
            if not host or host in configured_hosts:
                continue  # Skip missing hosts or plugs already set up
            
            entry_devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
            if not entry_devices:
                continue
                
            device = entry_devices[0]
            
            # Filter: only show devices whose LED subsystem we know how to
            # drive - single-outlet plugs (PLUGS_UI) and multi-outlet power
            # strips (POWERSTRIP_UI, e.g. "Shelly Power Strip 4 Gen4").
            model = device.model or ""
            model_lower = model.lower()
            if not any(keyword in model_lower for keyword in ("plug", "power strip", "powerstrip")):
                continue
                
            # Discover which room the plug is currently assigned to
            area_name = "Unassigned Room"
            if device.area_id:
                area = area_reg.async_get_area(device.area_id)
                if area and area.name:
                    area_name = area.name
            
            name = device.name_by_user or device.name or entry.title
            display_name = f"{name} ({area_name})"
            
            identifiers = [list(id_tuple) for id_tuple in device.identifiers]

            devices[host] = {
                "name": name,
                "display_name": display_name,
                "identifiers": identifiers
            }

        if not devices:
            return self.async_abort(reason="no_shelly_plugs_found")

        if user_input is not None:
            selected_host = user_input["shelly_device"]
            device_info = devices[selected_host]
            
            await self.async_set_unique_id(f"shelly_led_{selected_host}")
            self._abort_if_unique_id_configured()

            username, password = get_shelly_credentials(self.hass, selected_host)

            return self.async_create_entry(
                title=f"{device_info['name']} LED Ring",
                data={
                    "host": selected_host,
                    "name": device_info["name"],
                    "identifiers": device_info["identifiers"],
                    "username": username,
                    "password": password,
                }
            )

        dropdown_options = {host: info["display_name"] for host, info in devices.items()}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("shelly_device"): vol.In(dropdown_options)
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Handle reauth when the device rejects our stored credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        host = self._reauth_entry.data["host"]

        # Try to silently re-pull the current password from the official shelly entry.
        username, password = get_shelly_credentials(self.hass, host)
        if password and password != self._reauth_entry.data.get("password"):
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={
                    **self._reauth_entry.data,
                    "username": username or "admin",
                    "password": password,
                },
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Prompt for a password when it cannot be sourced automatically."""
        errors = {}
        host = self._reauth_entry.data["host"]

        if user_input is not None:
            username = user_input.get("username") or "admin"
            password = user_input["password"]

            client = ShellyRpcClient(
                async_get_clientsession(self.hass), host, username, password
            )
            try:
                await client.get_config()
            except ShellyAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        "username": username,
                        "password": password,
                    },
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Optional("username", default="admin"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
            description_placeholders={"host": host},
        )
