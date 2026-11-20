"""Thực thể weather.*: gom thời tiết hiện tại + dự báo theo giờ / theo ngày thành bản tin gọn cho màn hình."""
from __future__ import annotations

import logging
from typing import Any, Mapping

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Thứ tự cố định: màn hình (firmware) dùng cùng bảng này để chọn icon và chữ tiếng Việt
CONDITIONS = ("sunny", "clear-night", "partlycloudy", "cloudy", "rainy", "pouring", "lightning", "lightning-rainy",
              "snowy", "snowy-rainy", "hail", "fog", "windy", "windy-variant", "exceptional")
FEATURE_DAILY, FEATURE_HOURLY = 1, 2
HOURLY_STEP = 3                      # 5 mốc cách nhau 3 giờ
SLOTS = 5
WEEKDAYS = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN")
WIND_TO_KMH = {"km/h": 1.0, "m/s": 3.6, "mph": 1.609344, "kn": 1.852, "ft/s": 1.09728, "in/s": 0.09144}


def cond_index(c: Any) -> int:
    try:
        return CONDITIONS.index(str(c))
    except ValueError:
        return 3                      # không rõ -> coi như nhiều mây


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _i(v: Any, default: int = -1) -> int:
    n = _num(v)
    return int(round(n)) if n is not None else default


def supported(attrs: Mapping[str, Any]) -> list[str]:
    feat = int(attrs.get("supported_features") or 0)
    out = []
    if feat & FEATURE_HOURLY:
        out.append("hourly")
    if feat & FEATURE_DAILY:
        out.append("daily")
    return out


async def async_fetch(hass: HomeAssistant, entity_id: str, attrs: Mapping[str, Any]) -> dict[str, list]:
    """Gọi weather.get_forecasts cho từng kiểu mà thực thể hỗ trợ; lỗi thì bỏ qua kiểu đó."""
    res: dict[str, list] = {"hourly": [], "daily": []}
    for kind in supported(attrs):
        try:
            data = await hass.services.async_call(
                "weather", "get_forecasts", {"entity_id": entity_id, "type": kind},
                blocking=True, return_response=True)
            res[kind] = list((data or {}).get(entity_id, {}).get("forecast") or [])
        except Exception:  # noqa: BLE001 - nhà cung cấp lỗi / hết hạn mức: giữ dữ liệu rỗng
            _LOGGER.debug("Không lấy được dự báo %s của %s", kind, entity_id, exc_info=True)
    if not res["daily"] and not res["hourly"]:                  # tích hợp cũ: dự báo nằm trong thuộc tính
        res["daily"] = list(attrs.get("forecast") or [])
    return res


def _hourly(items: list[dict[str, Any]]) -> list[list]:
    now = dt_util.now()
    rows = []
    for it in items:
        t = dt_util.parse_datetime(str(it.get("datetime", "")))
        if t is None:
            continue
        t = dt_util.as_local(t)
        if t.timestamp() >= now.timestamp() - 1800:
            rows.append((t, it))
    out = []
    for t, it in rows[::HOURLY_STEP][:SLOTS]:
        out.append([t.strftime("%H:%M"), cond_index(it.get("condition")), _i(it.get("temperature")),
                    _i(it.get("precipitation_probability"))])
    return out


def _daily(items: list[dict[str, Any]]) -> list[list]:
    today = dt_util.now().date()
    out = []
    for it in items:
        t = dt_util.parse_datetime(str(it.get("datetime", "")))
        if t is None:
            continue
        d = dt_util.as_local(t).date()
        if d < today:
            continue
        label = "Hôm nay" if d == today else WEEKDAYS[d.weekday()]
        out.append([label, cond_index(it.get("condition")), _i(it.get("temperature")), _i(it.get("templow"))])
        if len(out) == SLOTS:
            break
    return out


def state_fields(state: str, attrs: Mapping[str, Any], fc: Mapping[str, list] | None) -> dict[str, Any]:
    fc = fc or {}
    hourly = _hourly(fc.get("hourly") or [])
    daily = _daily(fc.get("daily") or [])
    wind = _num(attrs.get("wind_speed"))
    if wind is not None:
        wind *= WIND_TO_KMH.get(str(attrs.get("wind_speed_unit") or "km/h"), 1.0)
    hi = daily[0][2] if daily else (max((h[2] for h in hourly), default=-999))
    lo = daily[0][3] if daily and daily[0][3] > -999 else (min((h[2] for h in hourly), default=-999))
    return {
        "wc": cond_index(state), "wt": _i(attrs.get("temperature"), -999),
        "wi": hi if hi != -999 else -999, "wl": lo if lo != -999 else -999,
        "wf": _i(attrs.get("apparent_temperature"), -999), "wh": _i(attrs.get("humidity")),
        "ww": int(round(wind)) if wind is not None else -1, "wu": _i(attrs.get("uv_index")),
        "wp": _num(attrs.get("precipitation")) if _num(attrs.get("precipitation")) is not None else -1,
        "wq": _i(attrs.get("pressure")),
        "fh": hourly, "fd": daily,
    }
