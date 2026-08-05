# Shelly Plug LED Ring Integration for Home Assistant

<p align="right">
  <a href="https://github.com/radioactive-bbs/shelly_plug_led"><img src="https://img.shields.io/badge/GitHub-radioactive--bbs%2Fshelly__plug__led-181717?logo=github&logoColor=white" alt="GitHub repository"></a>
</p>

> This is a fork of the original **[shelly_plug_led](https://github.com/ishiharas/shelly_plug_led)** by **[@ishiharas](https://github.com/ishiharas)** — all credit for the original design and implementation goes to them. This fork adds **Shelly Power Strip (Gen4)** support on top of it.

A custom Home Assistant integration that turns the built-in RGB LED(s) of your **Shelly Plug S (Gen2 / Gen3)** or **Shelly Power Strip (Gen4)** devices into independent, fully controllable smart light entities.

This integration interacts with the LED configuration engine. It allows you to 
- change colors
- apply dimming levels
- toggle the LED(s) on and off 

**without affecting the operational on/off power state of the actual smart plug/outlet relay(s)**.

<p align="center">
  <img src="custom_components/shelly_plug_led/brand/banner.png" alt="Alt text" width="468">
</p>

## Prerequisites
1. You must have your Shelly plug(s) or power strip already configured and active in Home Assistant via the **official built-in Shelly integration**.
2. Your hardware must be a Generation 2/3 local RPC plug (such as the standard Shelly Plus Plug S or newer variants) or a Generation 4 Shelly Power Strip.

## On-color vs. off-color

Each LED gets **two** light entities: e.g. `LED Ring` (the color shown while the relay is **on**) and `LED Ring Off Color` (shown while it's **off**). This mirrors the device's native "switch" LED mode, which already tracks that relay's own on/off state in firmware - so e.g. red-when-on / green-when-off needs no automation: set both colors once and the device handles the rest, even while Home Assistant is offline. Turning either entity off disables "switch" mode for the whole device (see below); turning it back on only ever rewrites its own color slot.

## Multi-outlet devices (Shelly Power Strip)

On a Power Strip, one `LED Outlet N` / `LED Outlet N Off Color` pair is created per physical outlet found in the device's LED config (`switch:0`..`switch:3`). Note that on current Power Strip Gen4 firmware, the device actually reports only a single shared color slot (`switch:0`) for the whole strip rather than one per outlet - each outlet's physical LED still tracks *its own* relay state using that shared on/off color pair, so per-outlet red/green still works correctly, it's just configured once for the whole strip rather than per outlet. There's also a firmware limitation to be aware of: the LED **mode** (off / power-tracking / static-color) is a single setting shared by everything on the device - turning any one LED entity off switches LED mode off for the entire device. The "Reset LEDs to Default" button likewise resets the whole device, not a single outlet or color slot.

---

## Installation

### Method 1: Via HACS (Recommended)
1. Open **HACS** in your Home Assistant sidebar.
2. Click the three dots `...` in the top-right corner and select **Custom repositories**.
3. Paste the URL of your GitHub repository into the *Repository* input.
4. Select **Integration** as the Category and click **Add**.
5. Find **Shelly Plug LED Ring** in the HACS interface and click **Download**.
6. **Restart Home Assistant Core** to load the custom workspace files.

### Method 2: Manual Installation
1. Download the project repository source archive.
2. Extract the archive and copy the folder `config/custom_components/shelly_plug_led` directly into your Home Assistant runtime directory.
3. **Restart Home Assistant Core**.

---

## Configuration

1. In Home Assistant, navigate to **Settings > Devices & Services**.
2. Click the **Add Integration** button in the bottom right corner.
3. Search for **Shelly Plug LED Ring** and select it.

---

## Credits

Originally created by **[@ishiharas](https://github.com/ishiharas)** — see the upstream project at [ishiharas/shelly_plug_led](https://github.com/ishiharas/shelly_plug_led). This fork ([@radioactive-bbs](https://github.com/radioactive-bbs)) builds on that work to add Shelly Power Strip (Gen4) multi-outlet support.
