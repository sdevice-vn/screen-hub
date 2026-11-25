"""WebSocket cho màn hình ESP32: /api/screen_hub/ws (xác thực bằng khóa riêng của thiết bị)."""
from __future__ import annotations

import asyncio
import hmac
import logging

from aiohttp import WSMsgType, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONF_KEY, DOMAIN, WS_URL
from .layout import entity_ids

_LOGGER = logging.getLogger(__name__)


class ScreenHubDeviceView(HomeAssistantView):
    url = WS_URL
    name = "api:screen_hub:ws"
    requires_auth = False          # tự xác thực bằng khóa thiết bị ở thông điệp đầu tiên

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def _find_hub(self, key: str):
        for hub in self.hass.data.get(DOMAIN, {}).values():
            if hmac.compare_digest(hub.entry.data[CONF_KEY], key):
                return hub
        return None

    def _key_known(self, key: str) -> bool:
        """Khóa thuộc về một config entry (kể cả entry chưa nạp xong khi HA mới khởi động hoặc đang reload)."""
        return any(
            isinstance(e.data.get(CONF_KEY), str) and hmac.compare_digest(e.data[CONF_KEY], key)
            for e in self.hass.config_entries.async_entries(DOMAIN)
        )

    async def get(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        hub = None
        try:
            first = await ws.receive_json(timeout=10)
            if first.get("type") != "auth" or not isinstance(first.get("key"), str):
                raise ValueError("thiếu auth")
            hub = self._find_hub(first["key"])
            if hub is None:
                # Khóa còn hợp lệ nhưng tích hợp chưa sẵn sàng -> màn hình giữ nguyên ghép cặp và tự kết nối lại sau vài giây
                await ws.send_json({"type": "auth_wait" if self._key_known(first["key"]) else "auth_invalid"})
                await ws.close()
                return ws
            await ws.send_json({"type": "auth_ok", "name": hub.entry.title})
            hub.clients.add(ws)
            for m in hub.layout_messages():
                await ws.send_json(m)
            for eid in entity_ids(hub.layout):
                if (m := hub.state_message(eid)):
                    await ws.send_json(m)

            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = msg.json()
                if data.get("type") == "call":
                    await hub.async_handle_call(str(data.get("e", "")), str(data.get("a", "")), data.get("v"), data.get("s"))
                elif data.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
        except (asyncio.TimeoutError, ValueError, TypeError, AttributeError):
            _LOGGER.debug("Kết nối màn hình bị từ chối/timeout")
        finally:
            if hub:
                hub.clients.discard(ws)
        return ws
