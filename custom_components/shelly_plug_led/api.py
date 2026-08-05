"""HTTP RPC client for Shelly Gen2/Gen3 devices with optional digest auth.

Shelly Gen2/Gen3 expose a JSON-RPC endpoint at ``POST http://{host}/rpc``.
When the device has authentication enabled it answers an unauthenticated
request with ``401`` and a ``WWW-Authenticate: Digest`` challenge
(RFC 7616, algorithm SHA-256, qop="auth"). The username is always ``admin``
and the realm (device id) is supplied by the server in the challenge.

This client makes every request auth-mode-agnostic: it tries without auth
first and only computes a digest response when the server actually challenges
with ``401``. That way it works whether auth is on or off, and survives the
user toggling auth mode at runtime without any reconfiguration.
"""

from __future__ import annotations

import hashlib
import logging
import secrets

import aiohttp

_LOGGER = logging.getLogger(__name__)

SHELLY_DOMAIN = "shelly"
DEFAULT_USERNAME = "admin"
TIMEOUT = 5

# RPC components that expose LED configuration, tried in this order until one
# answers. ``PLUGS_UI`` covers single-outlet devices (Shelly Plug S Gen2/Gen3,
# ...); ``POWERSTRIP_UI`` covers multi-outlet devices (Shelly Power Strip
# Gen4, with switch:0..switch:3). Both share the same ``leds.colors`` /
# ``leds.mode`` config shape, just keyed by a different set of RPC methods.
LED_UI_COMPONENTS = ("PLUGS_UI", "POWERSTRIP_UI")


class ShellyAuthError(Exception):
    """Raised when the device requires auth we cannot satisfy (401, no/invalid creds)."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _sanitize_challenge_value(value: str) -> str:
    """Strip characters that could break out of a quoted Digest header value.

    ``realm``/``nonce``/``opaque`` come verbatim from the device's
    WWW-Authenticate response and are interpolated into our own outgoing
    Authorization header as quoted strings - an embedded ``"`` (or a stray
    CR/LF) would corrupt that header's structure. The only party able to
    supply a malicious challenge here already has full visibility of this
    same connection (the device itself, or a LAN MITM), so this is
    defense-in-depth rather than a fix for a reachable exploit.
    """
    return value.replace('"', "").replace("\r", "").replace("\n", "")


def _parse_challenge(header: str) -> dict[str, str]:
    """Parse a ``WWW-Authenticate: Digest ...`` header into a dict of params."""
    header = header.strip()
    if header.lower().startswith("digest "):
        header = header[len("digest "):]

    params: dict[str, str] = {}
    # Split on commas that are not inside quotes.
    field = ""
    in_quotes = False
    fields: list[str] = []
    for char in header:
        if char == '"':
            in_quotes = not in_quotes
            field += char
        elif char == "," and not in_quotes:
            fields.append(field)
            field = ""
        else:
            field += char
    if field:
        fields.append(field)

    for item in fields:
        if "=" not in item:
            continue
        key, _, val = item.partition("=")
        params[key.strip().lower()] = val.strip().strip('"')
    return params


class ShellyRpcClient:
    """Minimal JSON-RPC client for a single Shelly device."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._host = host
        self._username = username or DEFAULT_USERNAME
        self._password = password
        self._url = f"http://{host}/rpc"
        self._ui_component: str | None = None

    def set_credentials(self, username: str | None, password: str | None) -> None:
        """Update credentials at runtime without rebuilding the client."""
        self._username = username or DEFAULT_USERNAME
        self._password = password

    def _build_digest_header(self, www_auth: str, method: str, uri: str) -> str:
        params = _parse_challenge(www_auth)
        realm = _sanitize_challenge_value(params.get("realm", ""))
        nonce = _sanitize_challenge_value(params.get("nonce", ""))
        qop = _sanitize_challenge_value(params.get("qop", "auth"))
        cnonce = secrets.token_hex(8)
        nc = "00000001"

        ha1 = _sha256(f"{self._username}:{realm}:{self._password}")
        ha2 = _sha256(f"{method}:{uri}")
        response = _sha256(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")

        parts = [
            f'username="{self._username}"',
            f'realm="{realm}"',
            f'nonce="{nonce}"',
            f'uri="{uri}"',
            "algorithm=SHA-256",
            f'response="{response}"',
            f"qop={qop}",
            f"nc={nc}",
            f'cnonce="{cnonce}"',
        ]
        if "opaque" in params:
            parts.append(f'opaque="{_sanitize_challenge_value(params["opaque"])}"')
        return "Digest " + ", ".join(parts)

    async def _handle(self, res: aiohttp.ClientResponse) -> dict:
        if res.status != 200:
            text = await res.text()
            raise RuntimeError(f"RPC error {res.status}: {text}")
        data = await res.json()
        if isinstance(data, dict) and "error" in data and data["error"]:
            raise RuntimeError(f"RPC error: {data['error']}")
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data

    async def call(self, method: str, params: dict | None = None) -> dict:
        """Invoke an RPC method, applying digest auth only if the device challenges."""
        payload = {"id": 1, "method": method, "params": params or {}}

        # First attempt without any Authorization header.
        async with self._session.post(self._url, json=payload, timeout=TIMEOUT) as res:
            if res.status != 401:
                return await self._handle(res)
            challenge = res.headers.get("WWW-Authenticate", "")
            await res.read()  # drain the connection

        if not self._password:
            raise ShellyAuthError(
                "Device requires authentication but no password is configured"
            )

        auth_header = self._build_digest_header(challenge, "POST", "/rpc")
        async with self._session.post(
            self._url, json=payload, headers={"Authorization": auth_header}, timeout=TIMEOUT
        ) as res:
            if res.status == 401:
                raise ShellyAuthError(
                    "Authentication rejected (bad password or stale nonce)"
                )
            return await self._handle(res)

    async def get_config(self) -> dict:
        """Fetch the LED config, auto-detecting which RPC component the device exposes.

        Verified against real hardware: a device answers exactly one of
        LED_UI_COMPONENTS (PLUGS_UI on a Plug S, POWERSTRIP_UI on a Power
        Strip Gen4) and 404s outright on the other, so first-success-wins is
        sufficient - no need to probe every component and compare results.
        The winner is cached, so later calls (and set_config) skip probing.
        """
        if self._ui_component:
            return await self.call(f"{self._ui_component}.GetConfig")

        last_err: Exception | None = None
        for component in LED_UI_COMPONENTS:
            try:
                result = await self.call(f"{component}.GetConfig")
            except ShellyAuthError:
                raise  # Conclusive - not a "wrong component" signal.
            except Exception as err:  # noqa: BLE001 - probing; any failure means "try next"
                last_err = err
                continue
            self._ui_component = component
            return result

        raise last_err or RuntimeError("Device exposes no supported LED UI component")

    async def set_config(self, config: dict) -> dict:
        if not self._ui_component:
            await self.get_config()  # Probe for the right component first.
        return await self.call(f"{self._ui_component}.SetConfig", {"config": config})


def find_shelly_entry(hass, host: str):
    """Return the official ``shelly`` config entry that matches ``host``, if any."""
    for entry in hass.config_entries.async_entries(SHELLY_DOMAIN):
        if (entry.data.get("host") or entry.data.get("ip")) == host:
            return entry
    return None


def get_shelly_credentials(hass, host: str) -> tuple[str | None, str | None]:
    """Source credentials for ``host`` from the official ``shelly`` integration.

    Returns ``(username, password)``. ``password`` is ``None`` when the device
    has auth disabled or no matching official entry exists.
    """
    entry = find_shelly_entry(hass, host)
    if not entry:
        return None, None
    return (entry.data.get("username") or DEFAULT_USERNAME, entry.data.get("password"))
