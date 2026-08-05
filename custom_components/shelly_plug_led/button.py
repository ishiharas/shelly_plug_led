from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ShellyAuthError

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
        """Handle the button press to revert the LED ring mode back to power tracking."""
        try:
            await self._client.set_config({"leds": {"mode": "power"}})
        except ShellyAuthError:
            pass  # Coordinator's next poll will surface the reauth flow.
        except Exception:
            pass

        await self.coordinator.async_request_refresh()
