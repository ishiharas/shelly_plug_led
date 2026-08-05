import asyncio
import logging
import re
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ShellyAuthError

DOMAIN = "shelly_plug_led"
_LOGGER = logging.getLogger(__name__)

# Matches the per-outlet keys Shelly uses inside ``leds.colors``
# (e.g. "switch:0" .. "switch:3" on a Power Strip). Other keys such as
# "power" (the power-tracking-mode brightness) are ignored.
_SWITCH_KEY_RE = re.compile(r"^switch:(\d+)$")


def _discover_switch_keys(coordinator_data: dict | None) -> list[str]:
    """Return the sorted ``switch:N`` keys present in the LED color config."""
    colors = (coordinator_data or {}).get("leds", {}).get("colors", {})
    keys = [key for key in colors if _SWITCH_KEY_RE.match(key)]
    keys.sort(key=lambda key: int(_SWITCH_KEY_RE.match(key).group(1)))
    return keys or ["switch:0"]  # Fall back to the single-outlet default.


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the light platform using configuration entry details.

    Creates two LED entities per outlet: one for the "on" color, one for the
    "off" color - matching the device's native switch-mode LED, which shows a
    different color depending on that outlet's own relay state. Single-outlet
    devices (Shelly Plug S) keep the original "LED Ring" name/unique_id for
    the on-color entity; multi-outlet devices (Shelly Power Strip) get one
    "LED Outlet N" pair per switch channel.
    """
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    switch_keys = _discover_switch_keys(coordinator.data)
    multi = len(switch_keys) > 1

    entities = []
    for switch_key in switch_keys:
        index = int(_SWITCH_KEY_RE.match(switch_key).group(1))
        if multi:
            ring_label = f"LED Outlet {index + 1}"
            base_suffix = f"led_{switch_key.replace(':', '_')}"
        else:
            # Keep the original unique_id so existing single-outlet installs
            # don't get a new entity_id after an update (display name is
            # independent of unique_id, so renaming it below is safe).
            ring_label = "LED Ring"
            base_suffix = "led_ring"

        entities.append(
            ShellyPlugLedRing(
                coordinator=coordinator,
                client=data["client"],
                host=data["host"],
                entry_id=entry.entry_id,
                identifiers=entry.data.get("identifiers", []),
                switch_key=switch_key,
                color_key="on",
                name=f"{ring_label} On Color",
                unique_suffix=base_suffix,
            )
        )
        entities.append(
            ShellyPlugLedRing(
                coordinator=coordinator,
                client=data["client"],
                host=data["host"],
                entry_id=entry.entry_id,
                identifiers=entry.data.get("identifiers", []),
                switch_key=switch_key,
                color_key="off",
                name=f"{ring_label} Off Color",
                unique_suffix=f"{base_suffix}_off",
            )
        )
    async_add_entities(entities)

class ShellyPlugLedRing(CoordinatorEntity, LightEntity):
    """Representation of one color slot of a Shelly LED, with Optimistic State Management.

    The device's native "switch" LED mode holds two colors per outlet - one
    shown while the outlet's relay is on, one while it's off - so each
    outlet gets two of these entities (``color_key="on"`` / ``"off"``), each
    writing only its own slot. This lets e.g. red-when-on/green-when-off be
    configured entirely in firmware: once set, the LED tracks that outlet's
    own relay state with no HA automation involved.
    """

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self,
        coordinator,
        client,
        host,
        entry_id,
        identifiers,
        switch_key: str = "switch:0",
        color_key: str = "on",
        name: str = "LED Ring On Color",
        unique_suffix: str = "led_ring",
    ):
        super().__init__(coordinator)
        self._client = client
        self._host = host
        self._switch_key = switch_key
        self._color_key = color_key  # "on" or "off" - which color slot this entity writes.
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        self._attr_name = name
        self._identifiers = identifiers
        self._attr_icon = "mdi:led-on" if color_key == "on" else "mdi:led-variant-outline"

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
        """Whether this LED's subsystem is in "switch" mode.

        Note: ``mode`` is a single firmware-wide setting shared by every
        color-slot entity on the device (both on/off entities, and - on
        multi-outlet devices - every outlet) - turning any one of them off
        disables "switch" mode for the whole device. Only the RGB
        color/brightness below is independently addressable per entity.
        """
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        return self.led_config.get("mode") == "switch"

    @property
    def brightness(self) -> int:
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness
        b = self.led_config.get("colors", {}).get(self._switch_key, {}).get(self._color_key, {}).get("brightness", 100)
        return round((b / 100) * 255)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        if self._optimistic_rgb is not None:
            return self._optimistic_rgb
        rgb = self.led_config.get("colors", {}).get(self._switch_key, {}).get(self._color_key, {}).get("rgb", [100, 100, 100])
        return (round((rgb[0]/100)*255), round((rgb[1]/100)*255), round((rgb[2]/100)*255))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state overrides once the coordinator refreshes successfully."""
        self._optimistic_is_on = None
        self._optimistic_brightness = None
        self._optimistic_rgb = None
        super()._handle_coordinator_update()

    async def _send_rpc(self, payload: dict):
        try:
            await self._client.set_config(payload["config"])
        except ShellyAuthError:
            # Let the coordinator surface the reauth flow on its next poll.
            await self.coordinator.async_request_refresh()
            return
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
                        self._switch_key: {
                            self._color_key: {"rgb": [r, g, b], "brightness": pct_b}
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
