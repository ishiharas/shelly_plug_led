# Shelly Plug LED Ring Integration for Home Assistant

<p align="right">
  <a href="https://github.com/ishiharas/shelly_plug_led"><img src="https://img.shields.io/badge/GitHub-ishiharas%2Fshelly__plug__led-181717?logo=github&logoColor=white" alt="GitHub repository"></a>
  <a href="https://github.com/ishiharas/shelly_plug_led/releases"><img src="https://img.shields.io/github/v/release/ishiharas/shelly_plug_led?label=release" alt="Latest release"></a>
  <a href="https://github.com/ishiharas/shelly_plug_led/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
</p>

A custom Home Assistant integration that turns the built-in RGB LED(s) of your **Shelly Plug S (Gen2 / Gen3)** or **Shelly Power Strip (Gen4)** devices into independent, fully controllable smart light entities — **without affecting the operational on/off power state of the actual smart plug/outlet relay(s)**.

<p align="center">
  <img src="screenshots/controls.png" alt="LED Ring On Color and Off Color toggles on the device's control card" width="380">
  &nbsp;&nbsp;
  <img src="screenshots/off-color-picker.png" alt="Color picker for LED Ring Off Color, set to green" width="260">
</p>

---

## Why this exists

Shelly Gen2/Gen3/Gen4 devices already expose their status-LED configuration over their local RPC API, but the official Home Assistant Shelly integration doesn't surface it as controllable entities. This integration adds a thin layer on top of your **existing** official Shelly device: it reuses that device's connection details and credentials, and adds a handful of `light`/`button` entities attached to the same device card — no separate device, no separate credentials to manage.

## Features

- **Color control** — pick any RGB color and brightness for the LED, independent of the relay's own on/off state.
- **Separate on-color / off-color** — the LED can show one color while the relay is on and a *different* color while it's off (e.g. red when on, green when off), configured once and then handled entirely by the device's own firmware — no Home Assistant automation needed, and it keeps working even while Home Assistant is offline or restarting.
- **Independent toggles** — the on-color and off-color entities switch on/off fully independently of each other; turning one off doesn't touch the other.
- **Reset to factory default** — a button to put the LED back into the device's original power-tracking indicator mode.
- **Multi-outlet aware** — automatically creates one on/off color pair per outlet on a Shelly Power Strip (see [caveat](#power-strip-caveat) below).
- **Auth-aware** — works whether or not the device has local RPC authentication enabled, and reuses the password already configured in the official Shelly integration (falling back to its own stored copy, with a reauth flow if that ever goes stale).

## Supported hardware

| Device family | Generation | Notes |
|---|---|---|
| Shelly Plug S | Gen2 / Gen3 | Local RPC (`PLUGS_UI` component) |
| Shelly Power Strip 4 | Gen4 | Local RPC (`POWERSTRIP_UI` component) — see the [Power Strip caveat](#power-strip-caveat) |

Any device must already be set up and reachable through the **official built-in Shelly integration** (local RPC, not cloud-only/BLE-only setups) before it can be added here.

---

## Installation

### Method 1: Via HACS (recommended)
1. Open **HACS** in your Home Assistant sidebar.
2. Search for **Shelly Plug LED Ring** in the HACS interface and click **Download**.
   - If it doesn't show up (e.g. on an older HACS version), add it manually first: three dots `...` → **Custom repositories** → `https://github.com/ishiharas/shelly_plug_led`, category **Integration**.
3. **Restart Home Assistant Core** to load it.

### Method 2: Manual installation
1. Download the [latest release](https://github.com/ishiharas/shelly_plug_led/releases) source archive (or clone the repo).
2. Copy the `custom_components/shelly_plug_led` folder into your Home Assistant `config/custom_components/` directory.
3. **Restart Home Assistant Core**.

---

## Configuration

1. Make sure the target plug/power strip is already set up via the official **Shelly** integration (Settings → Devices & Services).
2. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
3. Search for **Shelly Plug LED Ring** and select it.
4. Pick the device from the dropdown (only devices recognized as a supported plug or power strip are listed) and confirm.
5. Repeat per device — each Shelly plug/power strip needs its own config entry.

If the device requires authentication, credentials are pulled automatically from the official Shelly integration's entry for that device. If that ever fails (e.g. the official entry was removed or the password changed there without a corresponding update here), a **reauthentication** prompt will appear under **Settings → Devices & Services**.

---

## Entities created

For a **single-outlet** device (Shelly Plug S):

| Entity | Domain | What it controls |
|---|---|---|
| `LED Ring On Color` | `light` | Color/brightness shown while the relay is **on** |
| `LED Ring Off Color` | `light` | Color/brightness shown while the relay is **off** |
| `Reset LEDs to Default` | `button` | Puts the LED back into the device's factory power-tracking mode |

For a **Power Strip**, the same pair is created per outlet found in the device's LED configuration (currently `LED Outlet 1 On/Off Color` for the single shared slot the Gen4 firmware exposes — see below).

### On-color vs. off-color

Turning the **on-color** entity on/off engages/disengages the device's native "switch" LED mode and sets the color shown while the relay is on. Turning the **off-color** entity on/off does the same for the color shown while the relay is off. The two are fully independent:

- Turning an entity **on** engages switch mode (if not already) and writes only *that* entity's own color slot.
- Turning an entity **off** just dims *that* slot's brightness to 0 — it does **not** touch switch mode or the sibling entity, so the other color keeps working normally.
- To go back to the device's original factory indicator (power-draw color), or to make the LED dark for both states at once, use the **Reset LEDs to Default** button, or turn both entities off.

Because the color mapping is written straight to the device's own `leds` config, red-on/green-off (or any other combination) needs **no HA automation at all** — set both colors once and the firmware handles switching between them on every relay toggle, including while Home Assistant itself is offline.

### Power Strip caveat

On a Shelly Power Strip Gen4 (firmware 2.0.0, confirmed by testing against real hardware), the device only exposes **one shared** on/off color slot for the whole strip, not one per physical outlet, even though it has 4 individually switchable relays. In practice this doesn't stop per-outlet red/on-green/off from working: **each outlet's own LED independently tracks its own relay's state** using that one shared color pair, confirmed by testing — so setting on=red / off=green once still makes outlet 1's LED show red exactly when outlet 1 is on, independent of the other 3 outlets. Only the *color choice itself* isn't independently configurable per outlet on current firmware — if Shelly ships a firmware update that exposes `switch:1`..`switch:3` color slots individually, this integration will automatically create one on/off pair per outlet without any changes needed (it already discovers outlets dynamically from the device's own config).

The LED **mode** (off / power-tracking / switch) is also a single firmware-wide setting — the **Reset LEDs to Default** button resets it for the whole device, not per outlet or per color slot.

---

## Troubleshooting

- **"No compatible Shelly plugs or power strips found"** — the device must already exist as a config entry under the official **Shelly** integration (not just discovered), and its model needs to be recognized as a supported plug or power strip. Devices already configured in this integration are hidden from the list.
- **Re-authentication requested** — the stored password no longer works (e.g. it was changed on the device or in the official Shelly integration's config). Follow the reauth prompt under **Settings → Devices & Services**, or fix it in the official Shelly integration entry so it can be picked up automatically on the next restart/reload.
- **Colors look "washed out" or wrong** — the device's own RGB range is 0–100 (percent) internally; this integration converts to/from Home Assistant's 0–255 range, so values are rounded and won't always be pixel/byte-exact round-trips.
- **Reset button did nothing** — as of this integration's error-surfacing update, a failed reset now raises a visible error in Home Assistant instead of failing silently; check **Settings → System → Logs** for the underlying reason (commonly a stale/incorrect password).
- **Downloading diagnostics** — this integration ships a diagnostics provider (Settings → Devices & Services → the integration → Download diagnostics) that redacts the stored username/password automatically before sharing.

---

## Credits

Created by **[@ishiharas](https://github.com/ishiharas)**. Shelly Power Strip (Gen4) support, independent on/off color entities, and several reliability/security hardening fixes contributed by **[@radioactive-bbs](https://github.com/radioactive-bbs)**. See [Releases](https://github.com/ishiharas/shelly_plug_led/releases) for the full change history.

## License

MIT — see [LICENSE](LICENSE).
