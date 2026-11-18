"""Đèn (light.*): đọc trạng thái gửi xuống màn hình và đổi lệnh từ màn hình thành tham số light.turn_on."""
from __future__ import annotations

import colorsys
import math
from typing import Any, Mapping

from .const import LIGHT_COLORS, LIGHT_EFFECT, LIGHT_SCENES

_RGB_MODES = {"hs", "rgb", "rgbw", "rgbww", "xy"}
_CT_MODES = {"color_temp"} | _RGB_MODES   # HA tự quy đổi nhiệt độ màu cho đèn RGB
BR_TOLERANCE = 3        # % lệch cho phép khi nhận diện ngữ cảnh (đèn làm tròn độ sáng 0..255)
K_TOLERANCE = 150       # K lệch cho phép khi nhận diện ngữ cảnh


def _modes(attrs: Mapping[str, Any]) -> list[str]:
    return list(attrs.get("supported_color_modes") or [])


def can_brightness(attrs: Mapping[str, Any]) -> bool:
    return any(m != "onoff" for m in _modes(attrs))


def can_color_temp(attrs: Mapping[str, Any]) -> bool:
    return any(m in _CT_MODES for m in _modes(attrs))


def can_rgb(attrs: Mapping[str, Any]) -> bool:
    return any(m in _RGB_MODES for m in _modes(attrs))


def hue(attrs: Mapping[str, Any]) -> int:
    """Sắc độ 0..359 khi đèn đang ở chế độ màu (độ bão hoà đủ rõ); -1 nếu không biết / đang là ánh sáng trắng."""
    hs = attrs.get("hs_color")
    if attrs.get("color_mode") in _RGB_MODES and isinstance(hs, (list, tuple)) and len(hs) == 2:
        try:
            if float(hs[1]) >= 15:
                return int(round(float(hs[0]))) % 360
        except (TypeError, ValueError):
            pass
    return -1


def clamp_kelvin(attrs: Mapping[str, Any], k: int) -> int:
    lo = attrs.get("min_color_temp_kelvin") or 2000
    hi = attrs.get("max_color_temp_kelvin") or 6500
    return int(max(lo, min(hi, k)))


def brightness_pct(attrs: Mapping[str, Any]) -> int:
    b = attrs.get("brightness")
    if isinstance(b, (int, float)) and not isinstance(b, bool) and b > 0:
        return max(1, min(100, round(b * 100 / 255)))
    return -1


def _kelvin(attrs: Mapping[str, Any]) -> int | None:
    k = attrs.get("color_temp_kelvin")
    return int(k) if isinstance(k, (int, float)) and not isinstance(k, bool) and k > 0 else None


def color_id(attrs: Mapping[str, Any]) -> str:
    """Màu gần nhất trong 3 màu có sẵn (tính sau khi giới hạn theo dải của đèn); rỗng nếu không biết."""
    if hue(attrs) >= 0:
        return "rgb"
    if attrs.get("color_mode") in _RGB_MODES:
        return ""                             # màu trắng pha bằng RGB: không biết nhiệt độ màu
    k = _kelvin(attrs)
    if k is None:
        return ""
    return min(LIGHT_COLORS, key=lambda c: abs(clamp_kelvin(attrs, LIGHT_COLORS[c]) - k))


def _hue_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _kelvin_to_hs(kelvin: float) -> tuple[float, float]:
    """Nhiệt độ màu -> (sắc độ, bão hoà), cùng công thức HA dùng khi đổi K sang màu cho đèn RGB."""
    t = max(1000.0, min(40000.0, kelvin)) / 100
    red = 255.0 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    green = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    blue = 255.0 if t >= 66 else 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    r, g, b = (max(0.0, min(255.0, v)) / 255 for v in (red, green, blue))
    h, s, _ = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s * 100


def _scene_color_matches(spec: Mapping[str, Any], attrs: Mapping[str, Any]) -> bool:
    modes = _modes(attrs)
    mode = attrs.get("color_mode")
    hs = attrs.get("hs_color")
    cur_hs = None
    if mode in _RGB_MODES and isinstance(hs, (list, tuple)) and len(hs) == 2:
        try:
            cur_hs = (float(hs[0]), float(hs[1]))
        except (TypeError, ValueError):
            cur_hs = None
    if "hs" in spec and can_rgb(attrs):                      # màu theo sắc độ (tím / vàng)
        return cur_hs is not None and _hue_diff(cur_hs[0], spec["hs"][0]) <= 10 and cur_hs[1] >= spec["hs"][1] - 20
    if not can_color_temp(attrs):
        return True                                          # đèn không chỉnh màu: chỉ cần khớp độ sáng
    kk = clamp_kelvin(attrs, spec["kelvin"])
    if "color_temp" in modes:
        k = _kelvin(attrs)
        return mode in (None, "color_temp") and k is not None and abs(k - kk) <= K_TOLERANCE
    ref = _kelvin_to_hs(kk)                                  # đèn chỉ có RGB: so với màu HA quy đổi từ K
    return cur_hs is not None and _hue_diff(cur_hs[0], ref[0]) <= 10 and abs(cur_hs[1] - ref[1]) <= 12


def scene_id(state: str, attrs: Mapping[str, Any], effect_running: bool = False) -> str:
    """Ngữ cảnh đang áp dụng: effect / reading / relax / night; rỗng nếu không khớp hoặc đèn tắt."""
    if state != "on" or not can_brightness(attrs):
        return ""
    if effect_running:
        return LIGHT_EFFECT
    br = brightness_pct(attrs)
    for sid, spec in LIGHT_SCENES.items():
        if abs(br - spec["pct"]) <= BR_TOLERANCE and _scene_color_matches(spec, attrs):
            return sid
    return ""


def state_fields(state: str, attrs: Mapping[str, Any], effect_running: bool = False) -> dict[str, Any]:
    """Các trường thêm vào thông điệp `state` của entity light."""
    return {
        "br": brightness_pct(attrs),          # độ sáng 1..100 (-1: đang tắt / không biết)
        "cb": can_brightness(attrs),          # chỉnh được độ sáng
        "cc": can_color_temp(attrs),          # chỉnh được nhiệt độ màu
        "cr": can_rgb(attrs),                 # chỉnh được màu RGB
        "hu": hue(attrs),                     # sắc độ 0..359 (-1: không phải chế độ màu)
        "cl": color_id(attrs),                # warm / neutral / cool / rgb / ""
        "sc": scene_id(state, attrs, effect_running),   # effect / reading / relax / night / ""
    }


def service_data(action: str, value: Any, text: Any, attrs: Mapping[str, Any]) -> dict[str, Any] | None:
    """Tham số cho light.turn_on, hoặc None nếu lệnh không hợp lệ / đèn không hỗ trợ."""
    if action == "brightness":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not can_brightness(attrs):
            return None
        return {"brightness_pct": max(1, min(100, int(value)))}
    if action == "color":
        if text not in LIGHT_COLORS or not can_color_temp(attrs):
            return None
        return {"color_temp_kelvin": clamp_kelvin(attrs, LIGHT_COLORS[text])}
    if action == "hue":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not can_rgb(attrs):
            return None
        return {"hs_color": [int(value) % 360, 100]}
    if action == "scene":
        if text not in LIGHT_SCENES or not can_brightness(attrs):
            return None
        spec = LIGHT_SCENES[text]
        data: dict[str, Any] = {"brightness_pct": spec["pct"]}
        if "hs" in spec and can_rgb(attrs):
            data["hs_color"] = list(spec["hs"])
        elif can_color_temp(attrs):
            data["color_temp_kelvin"] = clamp_kelvin(attrs, spec["kelvin"])
        return data
    return None
