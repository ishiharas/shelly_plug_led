from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ShellyAuthError, ShellyRpcClient, get_shelly_credentials

DOMAIN = "shelly_plug_led"
_LOGGER = logging.getLogger(__name__)


def _resolve_credentials(hass: HomeAssistant, entry: ConfigEntry) -> tuple[str | None, str | None]:
    """Pick credentials live from the official shelly entry, with a stored fallback."""
    host = entry.data["host"]
    username, password = get_shelly_credentials(hass, host)
    if password is None:
        # No live match (entry gone/renamed, or auth off) - fall back to our copy.
        username = entry.data.get("username") or username
        password = entry.data.get("password")
    return username, password


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly Plug LED Ring from a config entry."""
    host = entry.data["host"]
    session = async_get_clientsession(hass)

    username, password = _resolve_credentials(hass, entry)
    client = ShellyRpcClient(session, host, username, password)

    # Keep our stored fallback in sync with what the official integration has.
    if (entry.data.get("username"), entry.data.get("password")) != (username, password):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "username": username, "password": password}
        )

    async def async_get_led_data():
        try:
            return await client.get_config()
        except ShellyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
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
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "host": host,
        "client": client,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, ["light", "button"])
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its data changes (e.g. after reauth)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the auth-aware schema."""
    if entry.version == 1:
        username, password = get_shelly_credentials(hass, entry.data["host"])
        new_data = {**entry.data}
        if password is not None:
            new_data["username"] = username or "admin"
            new_data["password"] = password
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["light", "button"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
