"""Screen Hub - màn hình điều khiển trung tâm ESP32-S3 cho Home Assistant."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import panel_api
from .const import DOMAIN, PANEL_URL, STATIC_URL
from .device_ws import ScreenHubDeviceView
from .hub import ScreenHub
from .layout import async_get_icons


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await async_get_icons(hass)          # đọc file icon một lần trong executor, giữ trong bộ nhớ
    hass.http.register_view(ScreenHubDeviceView(hass))
    panel_api.async_register(hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)])
    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass, webcomponent_name="screen-hub-panel", frontend_url_path=PANEL_URL,
        module_url=f"{STATIC_URL}/panel.js?v={version}", sidebar_title="Màn hình HA",
        sidebar_icon="mdi:monitor-dashboard", require_admin=True)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = ScreenHub(hass, entry)
    await hub.async_load()
    hass.data[DOMAIN][entry.entry_id] = hub
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = hass.data[DOMAIN].pop(entry.entry_id, None)
    if hub:
        await hub.async_shutdown()
    return True
