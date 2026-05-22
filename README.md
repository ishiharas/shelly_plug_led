# Shelly Plug LED Ring Integration for Home Assistant

A custom Home Assistant integration that turns the built-in RGB LED ring of your **Shelly Plug S (Gen2 / Gen3)** devices into an independent, fully controllable smart light entity. 

This integration interacts with the LED configuration engine. It allows you to 
- change colors
- apply dimming levels
- toggle the ring on and off 

**without affecting the operational on/off power state of the actual smart plug relay**.

<p align="center">
  <img src="images/banner.png" alt="Alt text" width="468">
</p>

## Prerequisites
1. You must have your Shelly plugs already configured and active in Home Assistant via the **official built-in Shelly integration**.
2. Your hardware must be Generation 2 or Generation 3 local RPC devices (such as the standard Shelly Plus Plug S or newer variants).

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
