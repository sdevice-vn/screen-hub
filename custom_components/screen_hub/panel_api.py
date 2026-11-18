"""Lệnh WebSocket của HA frontend cho panel cấu hình."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .layout import async_get_icons


def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_set)
    websocket_api.async_register_command(hass, ws_icons)


def _hub(hass, connection, msg):
    hub = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if hub is None:
        connection.send_error(msg["id"], "not_found", "Không tìm thấy màn hình")
    return hub


@websocket_api.websocket_command({vol.Required("type"): "screen_hub/list"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    connection.send_result(msg["id"], [
        {"entry_id": eid, "title": h.entry.title, "connected": h.connected}
        for eid, h in hass.data.get(DOMAIN, {}).items()])


@websocket_api.websocket_command(
    {vol.Required("type"): "screen_hub/get", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_get(hass, connection, msg):
    if (hub := _hub(hass, connection, msg)):
        connection.send_result(msg["id"], {"layout": hub.layout, "rev": hub.rev,
                                           "connected": hub.connected})


@websocket_api.websocket_command({
    vol.Required("type"): "screen_hub/set", vol.Required("entry_id"): str,
    vol.Required("layout"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set(hass, connection, msg):
    if not (hub := _hub(hass, connection, msg)):
        return
    try:
        await hub.async_set_layout(msg["layout"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    connection.send_result(msg["id"], {"rev": hub.rev})


@websocket_api.websocket_command({vol.Required("type"): "screen_hub/icons"})
@websocket_api.async_response
async def ws_icons(hass, connection, msg):
    connection.send_result(msg["id"], await async_get_icons(hass))
