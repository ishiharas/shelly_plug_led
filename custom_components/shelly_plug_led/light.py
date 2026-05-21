import asyncio
import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = "shelly_plug_led"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the light platform using configuration entry details."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ShellyPlugLedRing(
            coordinator=data["coordinator"],
            host=data["host"],
            entry_id=entry.entry_id,
            identifiers=entry.data.get("identifiers", [])
        )
    ])

class ShellyPlugLedRing(CoordinatorEntity, LightEntity):
    """Representation of the Shelly Plug LED Ring with Optimistic State Management."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, coordinator, host, entry_id, identifiers):
        super().__init__(coordinator)
        self._host = host
        self._session = None
        self._attr_unique_id = f"{entry_id}_led_ring"
        self._attr_name = "LED Ring"
        self._identifiers = identifiers
        self._attr_icon = "mdi:led-on"

        self._optimistic_is_on = None
        self._optimistic_brightness = None
        self._optimistic_rgb = None

    @property
    def device_info(self):
        """Link this custom entity to the existing native device entry card."""
        if self._identifiers:
            return {"identifiers": {tuple(i) for i in self._identifiers}}
        return None

    @property
    def led_config(self):
        """Safely fetch operational state lists."""
        return self.coordinator.data.get("leds", {})

    @property
    def is_on(self) -> bool:
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        return self.led_config.get("mode") == "switch"

    @property
    def brightness(self) -> int:
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness
        b = self.led_config.get("colors", {}).get("switch:0", {}).get("on", {}).get("brightness", 100)
        return round((b / 100) * 255)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        if self._optimistic_rgb is not None:
            return self._optimistic_rgb
        rgb = self.led_config.get("colors", {}).get("switch:0", {}).get("on", {}).get("rgb", [100, 100, 100])
        return (round((rgb[0]/100)*255), round((rgb[1]/100)*255), round((rgb[2]/100)*255))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state overrides once the coordinator refreshes successfully."""
        self._optimistic_is_on = None
        self._optimistic_brightness = None
        self._optimistic_rgb = None
        super()._handle_coordinator_update()

    async def _send_rpc(self, payload: dict):
        if not self._session:
            self._session = async_get_clientsession(self.hass)
        try:
            await self._session.post(f"http://{self._host}/rpc/PLUGS_UI.SetConfig", json=payload, timeout=5)
        except Exception as err:
            _LOGGER.error("Error communicating with Shelly LED Ring at %s: %s", self._host, err)
        
        await asyncio.sleep(1.5)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        rgb = kwargs.get("rgb_color", self.rgb_color)
        brightness = kwargs.get("brightness", self.brightness)

        self._optimistic_is_on = True
        self._optimistic_rgb = rgb
        self._optimistic_brightness = brightness
        self.async_write_ha_state()

        r = round((rgb[0] / 255) * 100)
        g = round((rgb[1] / 255) * 100)
        b = round((rgb[2] / 255) * 100)
        pct_b = round((brightness / 255) * 100)

        payload = {
            "config": {
                "leds": {
                    "mode": "switch",
                    "colors": {
                        "switch:0": {
                            "on": {"rgb": [r, g, b], "brightness": pct_b},
                            "off": {"rgb": [r, g, b], "brightness": pct_b}
                        }
                    }
                }
            }
        }
        await self._send_rpc(payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._optimistic_is_on = False
        self.async_write_ha_state()

        payload = {"config": {"leds": {"mode": "off"}}}
        await self._send_rpc(payload)
