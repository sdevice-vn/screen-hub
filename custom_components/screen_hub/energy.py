"""Biểu đồ điện năng tiêu thụ (ĐNTT) theo ngày: thiết bị ảo `energy.<id>`.

Người dùng chọn MỘT cảm biến điện năng cộng dồn (kWh, Wh, MWh...). Ở đây tính mức tiêu thụ của từng ngày bằng cách
cộng phần chênh lệch giữa hai lần đọc vào ngày hiện tại (giờ địa phương của HA), rồi lưu lại từng ngày.
Số liệu khoá theo entity_id của cảm biến nguồn nên xoá / thêm lại thẻ không mất lịch sử.

Phần này không phụ thuộc Home Assistant (chỉ `solar.read` khi cần) để test được độc lập.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from .const import ENERGY_KEEP_DAYS, ENERGY_RESET_RATIO


def _month_shift(y: int, m: int, delta: int) -> tuple[int, int]:
    i = y * 12 + (m - 1) + delta
    return i // 12, i % 12 + 1


class EnergyBook:
    """Sổ ghi điện năng từng ngày của một cảm biến cộng dồn."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        self.days: dict[str, float] = {}
        for k, v in (data.get("days") or {}).items():
            try:
                date.fromisoformat(k)
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f == f and f >= 0:
                self.days[k] = f
        last = data.get("last")
        self.last: float | None = float(last) if isinstance(last, (int, float)) and last == last and last >= 0 else None

    def to_dict(self) -> dict[str, Any]:
        return {"last": None if self.last is None else round(self.last, 4),
                "days": {k: round(v, 4) for k, v in sorted(self.days.items())}}

    # ---- ghi ---------------------------------------------------------------------------------
    def feed(self, value: float | None, day: date) -> bool:
        """Nhận một lần đọc cộng dồn (kWh), ghi phần tăng thêm vào `day`. Trả về True nếu số liệu đổi."""
        if value is None or value != value or value < 0:
            return False
        key = day.isoformat()
        if self.last is None:                       # lần đọc đầu tiên: chưa biết đã dùng bao nhiêu trước đó
            self.last = value
            self.days.setdefault(key, 0.0)
            return True
        delta = value - self.last
        if delta < 0:
            if value >= self.last * ENERGY_RESET_RATIO:
                return False                        # nhích xuống nhẹ (nhiễu): giữ mốc cũ, không tính
            delta = value                           # cảm biến đã reset về 0: đếm lại từ giá trị mới
        self.last = value
        before = self.days.get(key)
        self.days[key] = (before or 0.0) + delta
        return before is None or delta != 0

    def ensure_day(self, day: date) -> None:
        self.days.setdefault(day.isoformat(), 0.0)

    def prune(self, today: date) -> None:
        cut = (today - timedelta(days=ENERGY_KEEP_DAYS)).isoformat()
        for k in [k for k in self.days if k < cut]:
            del self.days[k]

    # ---- đọc ---------------------------------------------------------------------------------
    def month_values(self, y: int, m: int, upto: int | None = None) -> list[float | None]:
        """kWh từng ngày của tháng (ngày chưa có số liệu = None); `upto` = chỉ lấy đến ngày đó."""
        n = calendar.monthrange(y, m)[1]
        n = min(n, upto) if upto else n
        out: list[float | None] = []
        for d in range(1, n + 1):
            v = self.days.get(date(y, m, d).isoformat())
            out.append(None if v is None else round(v, 2))
        return out


def state_fields(book: EnergyBook | None, today: date) -> dict[str, Any]:
    """Các trường của bản tin `state` cho thiết bị ảo (xem EntState trong firmware)."""
    y, m = today.year, today.month
    py, pm = _month_shift(y, m, -1)
    out: dict[str, Any] = {
        "ey": y, "em": m, "ed": today.day,
        "dn": calendar.monthrange(y, m)[1], "w1": date(y, m, 1).weekday(),     # w1: thứ của ngày 1 (0 = Thứ 2 ... 6 = Chủ nhật)
        "pm": pm, "pdn": calendar.monthrange(py, pm)[1], "pw1": date(py, pm, 1).weekday(),
    }
    if book is None or not book.days:
        out["s"] = "unavailable"
        out["dk"], out["dp"] = [], []
        return out
    out["dk"] = book.month_values(y, m, today.day)       # tháng này, đến hôm nay
    out["dp"] = book.month_values(py, pm)                # tháng trước, cả tháng
    out["s"] = "ok"
    return out
