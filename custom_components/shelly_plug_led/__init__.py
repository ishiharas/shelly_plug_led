from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

DOMAIN = "shelly_plug_led"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly Plug LED Ring from a config entry."""
    host = entry.data["host"]
    session = async_get_clientsession(hass)

    async def async_get_led_data():
        try:
            async with session.get(f"http://{host}/rpc/PLUGS_UI.GetConfig", timeout=5) as res:
                if res.status != 200:
                    raise UpdateFailed(f"Error fetching config: {res.status}")
                return await res.json()
        except Exception as err:
            raise UpdateFailed(f"Communication error: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"shelly_led_{host}",
        update_method=async_get_led_data,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator, "host": host}
    
    await hass.config_entries.async_forward_entry_setups(entry, ["light", "button"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["light", "button"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
