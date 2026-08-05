import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ShellyAuthError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "shelly_plug_led"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the button platform using configuration entry details."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ShellyPlugLedResetButton(
            coordinator=data["coordinator"],
            client=data["client"],
            host=data["host"],
            entry_id=entry.entry_id,
            identifiers=entry.data.get("identifiers", [])
        )
    ])

class ShellyPlugLedResetButton(CoordinatorEntity, ButtonEntity):
    """Button to reset the Shelly LED(s) back to their out-of-the-box factory configuration.

    LED mode is a single firmware-wide setting (see ShellyPlugLedRing.is_on),
    so one button resets all outlets on multi-outlet devices too.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Reset LEDs to Default"
    _attr_icon = "mdi:restore"

    def __init__(self, coordinator, client, host, entry_id, identifiers):
        super().__init__(coordinator)
        self._client = client
        self._host = host
        self._identifiers = identifiers
        self._attr_unique_id = f"{entry_id}_led_reset_button"

    @property
    def device_info(self):
        """Link this button to the existing native device card profile."""
        if self._identifiers:
            return {"identifiers": {tuple(i) for i in self._identifiers}}
        return None

    async def async_press(self) -> None:
        """Handle the button press to revert the LED mode back to power tracking."""
        try:
            await self._client.set_config({"leds": {"mode": "power"}})
        except ShellyAuthError as err:
            # Let the coordinator surface the reauth flow, but still fail the
            # press visibly rather than silently pretending it worked.
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Shelly device at {self._host} rejected the request - re-authentication needed"
            ) from err
        except Exception as err:
            _LOGGER.error("Error resetting Shelly LED at %s: %s", self._host, err)
            raise HomeAssistantError(f"Failed to reset Shelly LED at {self._host}: {err}") from err

        await self.coordinator.async_request_refresh()
