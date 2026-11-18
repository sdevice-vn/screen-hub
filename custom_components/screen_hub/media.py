"""Loa / trình phát nhạc (media_player.*): đọc trạng thái gửi xuống màn hình và đổi lệnh thành dịch vụ media_player."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

# MediaPlayerEntityFeature
FEAT_VOLUME_SET = 4
FEAT_PREVIOUS = 16
FEAT_NEXT = 32
FEAT_SELECT_SOURCE = 2048

MAX_SOURCES = 12
MAX_TEXT = 60
_OFF = ("off", "standby")
_PLAYING = ("playing", "buffering")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def sources(attrs: Mapping[str, Any]) -> list[str]:
    return [str(s)[:24] for s in list(attrs.get("source_list") or [])[:MAX_SOURCES]]


def position(state: str, attrs: Mapping[str, Any], now: datetime | None = None) -> int:
    """Vị trí phát hiện tại (giây); đang phát thì cộng thời gian kể từ lúc HA cập nhật. -1 nếu không biết."""
    pos = _num(attrs.get("media_position"))
    if pos is None:
        return -1
    upd = attrs.get("media_position_updated_at")
    if state == "playing" and isinstance(upd, datetime):
        now = now or datetime.now(timezone.utc)
        pos += max(0.0, (now - upd).total_seconds())
    dur = _num(attrs.get("media_duration"))
    if dur:
        pos = min(pos, dur)
    return int(pos)


def state_fields(state: str, attrs: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    vol = _num(attrs.get("volume_level"))
    dur = _num(attrs.get("media_duration"))
    return {
        "ti": str(attrs.get("media_title") or "")[:MAX_TEXT],                                  # tên bài
        "ar": str(attrs.get("media_artist") or attrs.get("media_album_artist")
                  or attrs.get("app_name") or "")[:MAX_TEXT],                                  # ca sĩ / ứng dụng
        "vl": int(round(max(0.0, min(1.0, vol)) * 100)) if vol is not None else -1,           # âm lượng 0..100
        "mm": bool(attrs.get("is_volume_muted")),
        "mp": position(state, attrs, now),                                                    # giây
        "md": int(dur) if dur else -1,
        "sr": str(attrs.get("source") or "")[:24],
        "sl": sources(attrs),
        "mf": int(attrs.get("supported_features") or 0),
    }


def service_for(state: str, attrs: Mapping[str, Any], action: str, value: Any
                ) -> tuple[str, dict[str, Any]] | None:
    """(tên dịch vụ media_player, tham số thêm) hoặc None nếu lệnh không hợp lệ."""
    if action == "playpause":
        if state in _OFF:
            return "turn_on", {}
        return ("media_pause" if state in _PLAYING else "media_play"), {}
    if action == "next":
        return "media_next_track", {}
    if action == "prev":
        return "media_previous_track", {}
    if action == "power":
        return ("turn_on" if state in _OFF else "turn_off"), {}
    if action == "volume":
        v = _num(value)
        return ("volume_set", {"volume_level": max(0, min(100, int(v))) / 100}) if v is not None else None
    if action == "source":                                    # value = chỉ số trong source_list
        v = _num(value)
        lst = list(attrs.get("source_list") or [])
        if v is not None and 0 <= int(v) < min(len(lst), MAX_SOURCES):
            return "select_source", {"source": lst[int(v)]}
    return None
