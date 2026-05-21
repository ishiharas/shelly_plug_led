from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = "shelly_plug_led"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the button platform using configuration entry details."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ShellyPlugLedResetButton(
            coordinator=data["coordinator"],
            host=data["host"],
            entry_id=entry.entry_id,
            identifiers=entry.data.get("identifiers", [])
        )
    ])

class ShellyPlugLedResetButton(CoordinatorEntity, ButtonEntity):
    """Button to reset the Shelly Plug LED Ring back to its out-of-the-box factory configuration."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Reset LED Ring to Default"
    _attr_icon = "mdi:restore"

    def __init__(self, coordinator, host, entry_id, identifiers):
        super().__init__(coordinator)
        self._host = host
        self._identifiers = identifiers
        self._attr_unique_id = f"{entry_id}_led_reset_button"
        self._session = None

    @property
    def device_info(self):
        """Link this button to the existing native device card profile."""
        if self._identifiers:
            return {"identifiers": {tuple(i) for i in self._identifiers}}
        return None

    async def async_press(self) -> None:
        """Handle the button press to revert the LED ring mode back to power tracking."""
        if not self._session:
            self._session = async_get_clientsession(self.hass)
        
        payload = {"config": {"leds": {"mode": "power"}}}
        try:
            await self._session.post(f"http://{self._host}/rpc/PLUGS_UI.SetConfig", json=payload, timeout=5)
        except Exception:
            pass
        
        await self.coordinator.async_request_refresh()
