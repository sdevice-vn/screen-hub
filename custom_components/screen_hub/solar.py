"""Hệ thống năng lượng mặt trời (Inverter): gom nhiều cảm biến HA do người dùng chọn thành một thiết bị ảo `solar.<id>`.

Màn hình nhận một bản tin trạng thái duy nhất cho thiết bị ảo, gồm công suất (W), điện áp (V), dòng điện (A), phần trăm pin,
nhiệt độ và sản lượng hôm nay (kWh). Công suất ròng của pin và của lưới được tính ở đây (người dùng nhập riêng sạc/xả, lấy/đẩy lưới).
"""
from __future__ import annotations

from typing import Any, Mapping

# role -> (khoá ngắn gửi xuống màn hình, loại giá trị). Thứ tự = thứ tự hiển thị trong thẻ nhập của panel.
ROLES: dict[str, tuple[str, str]] = {
    "pv1_voltage": ("p1v", "volt"), "pv1_current": ("p1i", "amp"), "pv1_power": ("p1p", "power"),
    "pv2_voltage": ("p2v", "volt"), "pv2_current": ("p2i", "amp"), "pv2_power": ("p2p", "power"),
    "pv3_voltage": ("p3v", "volt"), "pv3_current": ("p3i", "amp"), "pv3_power": ("p3p", "power"),
    "battery_voltage": ("bv", "volt"), "battery_soc": ("bs", "percent"),
    "battery_charge_power": ("bc", "power"), "battery_discharge_power": ("bd", "power"),
    "grid_voltage": ("gv", "volt"), "grid_import_power": ("gi", "power"), "grid_export_power": ("ge", "power"),
    "load_power": ("lp", "power"), "ongrid_power": ("og", "power"),
    "backup_power": ("kp", "power"), "backup_voltage": ("kv", "volt"),
    "inverter_temp": ("it", "temp"), "yield_today": ("yd", "energy"),
}
STYLES = ("compact", "full")
_BAD = ("unknown", "unavailable", "none", "")


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f          # loại NaN


def convert(kind: str, value: float, unit: str) -> float:
    """Đưa về đơn vị chuẩn: công suất W, điện áp V, dòng điện A, nhiệt độ °C, sản lượng kWh, pin %."""
    u = (unit or "").strip()
    if kind == "power":
        return value * {"kW": 1000, "MW": 1e6, "mW": 0.001, "GW": 1e9}.get(u, 1)
    if kind == "energy":
        return value * {"Wh": 0.001, "MWh": 1000, "GWh": 1e6, "J": 1 / 3.6e6, "kJ": 1 / 3600, "MJ": 1 / 3.6}.get(u, 1)
    if kind == "volt":
        return value * {"mV": 0.001, "kV": 1000}.get(u, 1)
    if kind == "amp":
        return value * {"mA": 0.001, "kA": 1000}.get(u, 1)
    if kind == "temp":
        return (value - 32) * 5 / 9 if u in ("°F", "F") else value - 273.15 if u == "K" else value
    return value


def read(hass: Any, entity_id: str, kind: str) -> float | None:
    st = hass.states.get(entity_id) if entity_id else None
    if st is None or str(st.state).lower() in _BAD:
        return None
    v = _num(st.state)
    return None if v is None else convert(kind, v, st.attributes.get("unit_of_measurement", ""))


def state_fields(hass: Any, sensors: Mapping[str, str]) -> dict[str, Any]:
    """Các trường của bản tin `state` cho thiết bị ảo. Cảm biến lỗi / chưa có thì bỏ trường đó (màn hình hiện "--")."""
    vals: dict[str, float] = {}
    for role, eid in sensors.items():
        if role not in ROLES or not eid:
            continue
        v = read(hass, eid, ROLES[role][1])
        if v is not None:
            vals[role] = v
    out: dict[str, Any] = {}
    for role, v in vals.items():
        key, kind = ROLES[role]
        if kind == "power":
            out[key] = int(round(v))
        elif kind == "percent":
            out[key] = int(round(max(0, min(100, v))))
        else:
            out[key] = round(v, 1)
    # số string PV có khai báo cảm biến (1..3); màn hình chỉ vẽ các string này
    out["pn"] = max([i for i in (1, 2, 3) if any(sensors.get(f"pv{i}_{k}") for k in ("voltage", "current", "power"))] or [0])
    # string không khai báo công suất nhưng có áp & dòng thì tự tính P = U·I
    for i in (1, 2, 3):
        if f"p{i}p" not in out and f"p{i}v" in out and f"p{i}i" in out:
            out[f"p{i}p"] = int(round(out[f"p{i}v"] * out[f"p{i}i"]))
    # công suất ròng: pin (+ đang sạc), lưới (+ đang đẩy lên lưới)
    if "battery_charge_power" in vals or "battery_discharge_power" in vals:
        out["bp"] = int(round(vals.get("battery_charge_power", 0) - vals.get("battery_discharge_power", 0)))
    if "grid_import_power" in vals or "grid_export_power" in vals:
        out["gp"] = int(round(vals.get("grid_export_power", 0) - vals.get("grid_import_power", 0)))
    out["s"] = "ok" if vals else "unavailable"
    return out
