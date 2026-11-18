"""Hub: giữ layout của một màn hình, các kết nối WebSocket từ màn hình và đẩy trạng thái."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import web
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from . import light as light_util
from .const import (CLIMATE_DOMAIN, COVER_DOMAIN, COVER_FEATURE_SET_POSITION, DOMAIN, LIGHT_DOMAIN,
                    LIGHT_EFFECT, LIGHT_EFFECT_INTERVAL, LIGHT_EFFECT_MAX, LIGHT_EFFECT_MIN, LIGHT_EFFECT_STEP,
                    STORAGE_VERSION)
from .layout import async_get_icons, build_device_messages, entity_ids, validate_layout

_LOGGER = logging.getLogger(__name__)

EMPTY_LAYOUT: dict[str, Any] = {"floors": []}


class ScreenHub:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.layout: dict[str, Any] = EMPTY_LAYOUT
        self.rev = 0
        self.clients: set[web.WebSocketResponse] = set()
        self._unsub = None
        self._icons: list[dict[str, Any]] = []            # nạp trong async_load (không đọc file ở __init__)
        self._effects: dict[str, asyncio.Task] = {}      # entity_id -> tác vụ hiệu ứng tăng giảm độ sáng đang chạy

    async def async_load(self) -> None:
        self._icons = await async_get_icons(self.hass)     # cache dùng chung, đọc file trong executor
        data = await self._store.async_load()
        if data:
            try:
                self.layout = validate_layout(data["layout"])
                self.rev = int(data.get("rev", 0))
            except Exception:  # noqa: BLE001 - layout hỏng thì bắt đầu lại từ trống
                _LOGGER.exception("Layout lưu trữ không hợp lệ, dùng layout trống")
        self._resubscribe()

    async def async_set_layout(self, raw: dict[str, Any]) -> None:
        self.layout = validate_layout(raw)
        self.rev += 1
        await self._store.async_save({"layout": self.layout, "rev": self.rev})
        self._resubscribe()
        await self.async_push_layout()

    # ---- thông điệp xuống màn hình -------------------------------------------------
    def _friendly(self) -> dict[str, str]:
        out = {}
        for eid in entity_ids(self.layout):
            st = self.hass.states.get(eid)
            if st and st.attributes.get("friendly_name"):
                out[eid] = st.attributes["friendly_name"]
        return out

    def _device_classes(self) -> dict[str, str]:
        out = {}
        for eid in entity_ids(self.layout):
            st = self.hass.states.get(eid)
            if st and st.attributes.get("device_class"):
                out[eid] = st.attributes["device_class"]
        return out

    def layout_messages(self) -> list[dict[str, Any]]:
        return build_device_messages(self.layout, self._icons, self._friendly(), self.rev,
                                     self._device_classes())

    def state_message(self, entity_id: str) -> dict[str, Any] | None:
        st = self.hass.states.get(entity_id)
        if st is None:
            return None
        msg = {
            "type": "state", "e": entity_id, "s": st.state,
            "u": st.attributes.get("unit_of_measurement", ""),
            "dc": st.attributes.get("device_class", ""),
        }
        if entity_id.split(".", 1)[0] == COVER_DOMAIN:
            pos = st.attributes.get("current_position")
            msg["p"] = int(pos) if isinstance(pos, (int, float)) else -1       # 0 = đóng, 100 = mở
            feat = st.attributes.get("supported_features") or 0
            msg["sp"] = bool(int(feat) & COVER_FEATURE_SET_POSITION)           # có hỗ trợ đặt vị trí %
        elif entity_id.split(".", 1)[0] == CLIMATE_DOMAIN:
            a = st.attributes
            msg["u"] = self.hass.config.units.temperature_unit               # °C hoặc °F
            msg["tt"] = a.get("temperature")                                 # nhiệt độ mục tiêu
            msg["ct"] = a.get("current_temperature")                         # nhiệt độ phòng
            msg["mn"] = a.get("min_temp", 16)
            msg["mx"] = a.get("max_temp", 30)
            msg["stp"] = a.get("target_temp_step") or 1
            msg["hm"] = list(a.get("hvac_modes") or [])
            msg["fm"] = list(a.get("fan_modes") or [])
            msg["fan"] = a.get("fan_mode")
            msg["ha"] = a.get("hvac_action")
        elif entity_id.split(".", 1)[0] == LIGHT_DOMAIN:
            msg.update(light_util.state_fields(st.state, st.attributes, entity_id in self._effects))
        return msg

    async def async_push_layout(self) -> None:
        for m in self.layout_messages():
            await self._broadcast(m)
        for eid in entity_ids(self.layout):
            if (m := self.state_message(eid)):
                await self._broadcast(m)

    async def _broadcast(self, msg: dict[str, Any]) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except ConnectionError:
                self.clients.discard(ws)

    # ---- theo dõi thay đổi trạng thái ------------------------------------------------
    def _resubscribe(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        ids = entity_ids(self.layout)
        for eid in list(self._effects):
            if eid not in ids:
                self._stop_effect(eid)
        if ids:
            self._unsub = async_track_state_change_event(self.hass, ids, self._on_state)

    @callback
    def _on_state(self, event: Event) -> None:
        eid = event.data["entity_id"]
        new = event.data.get("new_state")
        if eid in self._effects and (new is None or new.state != "on"):
            self._stop_effect(eid)                     # đèn tắt / mất kết nối -> dừng hiệu ứng
        if (m := self.state_message(eid)):
            self.hass.async_create_task(self._broadcast(m))

    # ---- hiệu ứng tăng giảm độ sáng tự động ----------------------------------------------
    def _stop_effect(self, entity_id: str, notify: bool = True) -> bool:
        task = self._effects.pop(entity_id, None)
        if task is None:
            return False
        task.cancel()
        if notify and (m := self.state_message(entity_id)):       # báo màn hình bỏ nhãn "Hiệu ứng"
            self.hass.async_create_task(self._broadcast(m))
        return True

    async def _start_effect(self, entity_id: str) -> None:
        st = self.hass.states.get(entity_id)
        if st is None or not light_util.can_brightness(st.attributes):
            return
        self._stop_effect(entity_id, notify=False)
        # Sóng tam giác: min -> max -> min ... bắt đầu từ mức gần độ sáng hiện tại (đang tắt thì từ mức thấp nhất)
        up = list(range(LIGHT_EFFECT_MIN, LIGHT_EFFECT_MAX + 1, LIGHT_EFFECT_STEP))
        wave = up + up[-2:0:-1]
        cur = light_util.brightness_pct(st.attributes) if st.state == "on" else LIGHT_EFFECT_MIN
        start = min(range(len(up)), key=lambda i: abs(up[i] - cur))
        self._effects[entity_id] = self.hass.async_create_background_task(
            self._run_effect(entity_id, wave, start), f"{DOMAIN}_light_effect_{entity_id}")
        if (m := self.state_message(entity_id)):
            await self._broadcast(m)

    async def _run_effect(self, entity_id: str, wave: list[int], i: int) -> None:
        try:
            while True:
                await self.hass.services.async_call(
                    "light", "turn_on",
                    {"entity_id": entity_id, "brightness_pct": wave[i % len(wave)], "transition": LIGHT_EFFECT_INTERVAL},
                    blocking=False)
                i += 1
                await asyncio.sleep(LIGHT_EFFECT_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception:                                          # noqa: BLE001 - lỗi dịch vụ: dừng hiệu ứng, không làm sập tích hợp
            _LOGGER.exception("Hiệu ứng đèn %s bị dừng do lỗi", entity_id)
            self._effects.pop(entity_id, None)

    # ---- lệnh từ màn hình ----------------------------------------------------------
    async def async_handle_call(self, entity_id: str, action: str, value: Any = None,
                                text: Any = None) -> None:
        if entity_id not in entity_ids(self.layout):      # chỉ điều khiển entity đã chọn
            _LOGGER.warning("Màn hình yêu cầu entity ngoài layout: %s", entity_id)
            return
        domain = entity_id.split(".", 1)[0]
        if domain == LIGHT_DOMAIN:
            if action == "scene" and text == LIGHT_EFFECT:
                await self._start_effect(entity_id)
                return
            self._stop_effect(entity_id)                  # mọi lệnh khác lên đèn đều dừng hiệu ứng
        service: tuple[str, str] | None = None
        data: dict[str, Any] = {"entity_id": entity_id}
        if domain == COVER_DOMAIN:
            service = {"open": ("cover", "open_cover"), "close": ("cover", "close_cover"),
                       "stop": ("cover", "stop_cover"), "toggle": ("cover", "toggle")}.get(action)
            if action == "position" and isinstance(value, (int, float)) and not isinstance(value, bool):
                service = ("cover", "set_cover_position")
                data["position"] = max(0, min(100, int(value)))
        elif domain == CLIMATE_DOMAIN:
            st = self.hass.states.get(entity_id)
            attrs = st.attributes if st else {}
            if action == "set_temp" and isinstance(value, (int, float)) and not isinstance(value, bool):
                lo, hi = float(attrs.get("min_temp", 16)), float(attrs.get("max_temp", 30))
                data["temperature"] = max(lo, min(hi, float(value) / 10.0))    # màn hình gửi nhiệt độ × 10
                service = ("climate", "set_temperature")
            elif action == "set_hvac" and isinstance(text, str) and text in (attrs.get("hvac_modes") or []):
                data["hvac_mode"] = text
                service = ("climate", "set_hvac_mode")
            elif action == "set_fan" and isinstance(text, str) and text in (attrs.get("fan_modes") or []):
                data["fan_mode"] = text
                service = ("climate", "set_fan_mode")
        elif domain == LIGHT_DOMAIN and action in ("brightness", "color", "scene", "hue"):
            st = self.hass.states.get(entity_id)
            extra = light_util.service_data(action, value, text, st.attributes if st else {})
            if extra is not None:
                data.update(extra)
                service = ("light", "turn_on")
        elif action == "toggle":
            if domain == "lock":
                st = self.hass.states.get(entity_id)
                service = ("lock", "unlock" if st and st.state == "locked" else "lock")
            else:
                service = ("homeassistant", "toggle")
        elif action == "press":
            service = {"scene": ("scene", "turn_on"), "script": ("script", "turn_on"),
                       "button": ("button", "press")}.get(domain)
        if service is None:
            _LOGGER.debug("Bỏ qua lệnh %s cho %s", action, entity_id)
            return
        await self.hass.services.async_call(service[0], service[1], data, blocking=False)

    @property
    def connected(self) -> bool:
        return bool(self.clients)

    async def async_shutdown(self) -> None:
        for eid in list(self._effects):
            self._stop_effect(eid, notify=False)
        if self._unsub:
            self._unsub()
        for ws in list(self.clients):
            await ws.close()
