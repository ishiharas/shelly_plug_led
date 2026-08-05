"""Diagnostics support for Shelly Plug LED Ring.

This integration stores its own copy of the Shelly device's username/
password (see api.get_shelly_credentials / __init__._resolve_credentials)
as a resilience fallback for when the official ``shelly`` config entry is
unavailable. That's a second at-rest copy of the credential alongside the
official integration's own - this file makes sure Home Assistant's
"Download diagnostics" feature redacts it here too, the same way it
already redacts the official integration's copy.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "shelly_plug_led"
TO_REDACT = {"password", "username"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, with credentials redacted."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "led_config": coordinator.data if coordinator else None,
    }
