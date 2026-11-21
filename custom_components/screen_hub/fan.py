"""Quạt (fan.*): đọc trạng thái gửi xuống màn hình và đổi lệnh từ màn hình thành dịch vụ fan.*.

Màn hình chỉ hiện các điều khiển mà quạt hỗ trợ (supported_features): tốc độ %, đảo gió, chiều quay, chế độ gió (preset).
"""
from __future__ import annotations

from typing import Any, Mapping

from .const import FAN_FEATURE_DIRECTION, FAN_FEATURE_OSCILLATE, FAN_FEATURE_PRESET, FAN_FEATURE_SET_SPEED

DIRECTIONS = ("forward", "reverse")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else None


def state_fields(attrs: Mapping[str, Any]) -> dict[str, Any]:
    """Các trường của bản tin `state` cho quạt (xem EntState trong firmware)."""
    feat = int(_num(attrs.get("supported_features")) or 0)
    pct = _num(attrs.get("percentage"))
    step = _num(attrs.get("percentage_step"))
    osc = attrs.get("oscillating")
    presets = [str(p) for p in (attrs.get("preset_modes") or [])]
    return {
        "ffe": feat,                                                   # supported_features của HA
        "fpc": int(round(pct)) if pct is not None else -1,             # tốc độ 0..100 (-1 = không biết)
        "fst": round(step, 2) if step and step > 0 else 1,             # bước tốc độ (quạt 3 cấp: 33.33)
        "fos": 1 if osc is True else 0 if osc is False else -1,        # đang đảo gió
        "fdr": attrs.get("direction") if attrs.get("direction") in DIRECTIONS else "",
        "fpm": str(attrs.get("preset_mode") or ""),
        "fpl": presets if feat & FAN_FEATURE_PRESET else [],
    }


def service_for(attrs: Mapping[str, Any], action: str, value: Any, text: Any) -> tuple[str, dict[str, Any]] | None:
    """(tên dịch vụ trong domain fan, dữ liệu thêm) cho lệnh từ màn hình, hoặc None nếu không hợp lệ / quạt không hỗ trợ."""
    feat = int(_num(attrs.get("supported_features")) or 0)
    v = _num(value)
    if action == "power" and v is not None:
        return ("turn_on" if v else "turn_off"), {}
    if action == "speed" and v is not None and feat & FAN_FEATURE_SET_SPEED:
        return "set_percentage", {"percentage": max(0, min(100, int(round(v))))}
    if action == "oscillate" and v is not None and feat & FAN_FEATURE_OSCILLATE:
        return "oscillate", {"oscillating": bool(v)}
    if action == "direction" and text in DIRECTIONS and feat & FAN_FEATURE_DIRECTION:
        return "set_direction", {"direction": text}
    if action == "preset" and isinstance(text, str) and text in (attrs.get("preset_modes") or []) and feat & FAN_FEATURE_PRESET:
        return "set_preset_mode", {"preset_mode": text}
    return None
