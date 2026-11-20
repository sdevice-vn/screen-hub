"""Kiểm tra / chuẩn hoá layout (Tầng -> Phòng -> Thiết bị) và dựng thông điệp gửi xuống màn hình."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant

from .solar import ROLES as SOLAR_ROLES

from .const import (ACTION_DOMAINS, CARD_WIDTHS, CLIMATE_DOMAIN, COVER_DOMAIN, COVER_STYLES, CURTAIN_CLASSES, DEFAULT_ICON, ICONS_KEY, MAX_DEVICES_PER_ROOM, MAX_DEVICES_TOTAL,
                    MEDIA_DOMAIN, SOLAR_DOMAIN, SOLAR_STYLES, WEATHER_DOMAIN, WEATHER_STYLES,
                    MAX_FLOORS, MAX_NAME_LEN, MAX_ROOMS_PER_FLOOR, SUPPORTED_DOMAINS,
                    TOGGLE_DOMAINS)

_ICONS_FILE = Path(__file__).with_name("mdi_icons.json")


def load_icons() -> list[dict[str, Any]]:
    """Đọc file icon từ đĩa (I/O chặn). KHÔNG gọi trực tiếp trong event loop - dùng async_get_icons."""
    return json.loads(_ICONS_FILE.read_text(encoding="utf-8"))["icons"]


async def async_get_icons(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Trả về danh sách icon đã cache trong bộ nhớ; chỉ đọc file đúng một lần (trong executor)."""
    icons = hass.data.get(ICONS_KEY)
    if icons is None:
        icons = await hass.async_add_executor_job(load_icons)
        hass.data[ICONS_KEY] = icons
    return icons


def _name(v: Any) -> str:
    s = str(v).strip()
    if not s:
        raise vol.Invalid("tên không được để trống")
    if len(s) > MAX_NAME_LEN:
        raise vol.Invalid(f"tên tối đa {MAX_NAME_LEN} ký tự")
    return s


def _entity_id(v: Any) -> str:
    s = str(v).strip().lower()
    if "." not in s or s.split(".", 1)[0] not in SUPPORTED_DOMAINS:
        raise vol.Invalid(f"entity không được hỗ trợ: {s}")
    return s


def _solar_sensors(v: Any) -> dict[str, str]:
    """Bảng role -> entity_id cảm biến của Inverter; bỏ qua ô để trống."""
    if not isinstance(v, dict):
        raise vol.Invalid("sensors phải là bảng role -> entity_id")
    out: dict[str, str] = {}
    for role, eid in v.items():
        if role not in SOLAR_ROLES:
            raise vol.Invalid(f"role không hợp lệ: {role}")
        eid = str(eid or "").strip().lower()
        if not eid:
            continue
        if "." not in eid or eid.split(".", 1)[0] not in ("sensor", "input_number", "number"):
            raise vol.Invalid(f"cảm biến không hợp lệ: {eid}")
        out[role] = eid
    return out


DEVICE_SCHEMA = vol.Schema({
    vol.Required("entity_id"): _entity_id,
    vol.Optional("name", default=""): vol.Any("", _name),   # rỗng = dùng friendly_name của HA
    vol.Optional("icon", default=""): str,
    vol.Optional("cover_style", default=""): vol.In(("",) + COVER_STYLES),   # chỉ dùng cho cover.*
    vol.Optional("weather_style", default="compact"): vol.In(WEATHER_STYLES),   # chỉ dùng cho weather.*
    vol.Optional("solar_style", default="compact"): vol.In(SOLAR_STYLES),       # chỉ dùng cho solar.* (Inverter)
    vol.Optional("sensors", default=dict): _solar_sensors,                      # chỉ dùng cho solar.*: role -> cảm biến
    vol.Optional("width", default=1): vol.In(CARD_WIDTHS),                  # độ rộng thẻ (chỉ dùng cho sensor)
})
ROOM_SCHEMA = vol.Schema({
    vol.Required("id"): str,
    vol.Required("name"): _name,
    vol.Optional("devices", default=list): vol.All([DEVICE_SCHEMA], vol.Length(max=MAX_DEVICES_PER_ROOM)),
})
FLOOR_SCHEMA = vol.Schema({
    vol.Required("id"): str,
    vol.Required("name"): _name,
    vol.Optional("rooms", default=list): vol.All([ROOM_SCHEMA], vol.Length(max=MAX_ROOMS_PER_FLOOR)),
})
LAYOUT_SCHEMA = vol.Schema({
    vol.Required("floors"): vol.All([FLOOR_SCHEMA], vol.Length(max=MAX_FLOORS)),
})


def validate_layout(raw: dict[str, Any]) -> dict[str, Any]:
    layout = LAYOUT_SCHEMA(raw)
    total = sum(len(r["devices"]) for f in layout["floors"] for r in f["rooms"])
    if total > MAX_DEVICES_TOTAL:
        raise vol.Invalid(f"tối đa {MAX_DEVICES_TOTAL} thiết bị")
    return layout


def tile_type(entity_id: str) -> str:
    domain = entity_id.split(".", 1)[0]
    if domain == COVER_DOMAIN:
        return "cover"
    if domain == CLIMATE_DOMAIN:
        return "climate"
    if domain == MEDIA_DOMAIN:
        return "media"
    if domain == WEATHER_DOMAIN:
        return "weather"
    if domain == SOLAR_DOMAIN:
        return "solar"
    if domain in TOGGLE_DOMAINS:
        return "toggle"
    if domain in ACTION_DOMAINS:
        return "action"
    return "sensor"


def entity_ids(layout: dict[str, Any]) -> list[str]:
    seen: dict[str, None] = {}
    for f in layout["floors"]:
        for r in f["rooms"]:
            for d in r["devices"]:
                seen[d["entity_id"]] = None
    return list(seen)


def watch_ids(layout: dict[str, Any]) -> list[str]:
    """Các entity thật của HA cần theo dõi: thiết bị thường + cảm biến của từng Inverter (thiết bị ảo không có state)."""
    seen: dict[str, None] = {}
    for f in layout["floors"]:
        for r in f["rooms"]:
            for d in r["devices"]:
                if d["entity_id"].split(".", 1)[0] == SOLAR_DOMAIN:
                    for eid in (d.get("sensors") or {}).values():
                        seen[eid] = None
                else:
                    seen[d["entity_id"]] = None
    return list(seen)


def solar_devices(layout: dict[str, Any]) -> dict[str, dict[str, str]]:
    """entity_id ảo của Inverter -> bảng cảm biến."""
    return {d["entity_id"]: d.get("sensors") or {} for f in layout["floors"] for r in f["rooms"]
            for d in r["devices"] if d["entity_id"].split(".", 1)[0] == SOLAR_DOMAIN}


def default_cover_style(device_class: str) -> str:
    return "curtain_both" if device_class in CURTAIN_CLASSES else "roller"


def build_device_layout(layout: dict[str, Any], icons: list[dict[str, Any]],
                        friendly: dict[str, str],
                        device_classes: dict[str, str] | None = None) -> dict[str, Any]:
    """Layout rút gọn: icon đã đổi sang codepoint, loại tile đã xác định."""
    cp = {i["name"]: i["cp"] for i in icons}
    out_floors = []
    for f in layout["floors"]:
        rooms = []
        for r in f["rooms"]:
            devs = []
            for d in r["devices"]:
                eid = d["entity_id"]
                icon = d["icon"] or DEFAULT_ICON.get(eid.split(".", 1)[0], "mdi:eye")
                dev = {
                    "e": eid,
                    "n": d["name"] or friendly.get(eid) or eid.split(".", 1)[1],
                    "i": cp.get(icon, cp.get("mdi:eye", 0)),
                    "t": tile_type(eid),
                }
                if dev["t"] == "sensor" and d.get("width", 1) != 1:
                    dev["w"] = int(round(float(d["width"]) * 2))    # đơn vị nửa cột: 3 = ×1.5, 4 = ×2
                if dev["t"] == "weather" and d.get("weather_style") == "full":
                    dev["ws"] = "full"                          # mặc định (thu nhỏ) thì không gửi
                if dev["t"] == "solar" and d.get("solar_style") == "full":
                    dev["ws"] = "full"
                if dev["t"] == "cover":
                    dev["cs"] = d.get("cover_style") or default_cover_style((device_classes or {}).get(eid, ""))
                devs.append(dev)
            rooms.append({"n": r["name"], "d": devs})
        out_floors.append({"n": f["name"], "r": rooms})
    return {"f": out_floors}


def build_device_messages(layout: dict[str, Any], icons: list[dict[str, Any]],
                          friendly: dict[str, str], rev: int,
                          device_classes: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Chia layout thành nhiều thông điệp nhỏ (mỗi phòng một tin) vì thư viện WebSocket trên
    ESP32 giới hạn ~15KB mỗi tin. Màn hình chỉ áp dụng layout khi nhận `layout_end`."""
    compact = build_device_layout(layout, icons, friendly, device_classes)["f"]
    msgs: list[dict[str, Any]] = [
        {"type": "layout_begin", "rev": rev, "floors": [f["n"] for f in compact]}]
    for fi, f in enumerate(compact):
        for r in f["r"]:
            msgs.append({"type": "room", "rev": rev, "fi": fi, "n": r["n"], "d": r["d"]})
    msgs.append({"type": "layout_end", "rev": rev})
    return msgs
