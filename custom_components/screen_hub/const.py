"""Hằng số cho Screen Hub."""
DOMAIN = "screen_hub"
ICONS_KEY = f"{DOMAIN}_icons"          # hass.data: danh sách icon đã nạp sẵn (chỉ đọc)
STORAGE_VERSION = 1
WS_URL = "/api/screen_hub/ws"
STATIC_URL = "/screen_hub_static"
PANEL_URL = "screen-hub"

CONF_DEVICE_ID = "device_id"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_KEY = "key"

DEVICE_HTTP_PORT = 80

# Giới hạn để layout nằm gọn trong RAM của ESP32
MAX_FLOORS = 8
MAX_ROOMS_PER_FLOOR = 12
MAX_DEVICES_PER_ROOM = 40
MAX_DEVICES_TOTAL = 200
MAX_NAME_LEN = 24

# domain -> kiểu tile trên màn hình
TOGGLE_DOMAINS = {"switch", "light", "fan", "input_boolean", "automation", "lock"}
COVER_DOMAIN = "cover"
ACTION_DOMAINS = {"scene", "script", "button"}
SENSOR_DOMAINS = {"sensor", "binary_sensor"}
WEATHER_DOMAIN = "weather"           # thẻ thời tiết: thu nhỏ (chạm để mở) hoặc toàn màn hình
WEATHER_STYLES = ("compact", "full")
WEATHER_REFRESH_S = 20 * 60         # chu kỳ lấy lại dự báo
SOLAR_DOMAIN = "solar"                # thiết bị ảo "Inverter": gom nhiều cảm biến thành một thẻ năng lượng mặt trời
SOLAR_STYLES = ("compact", "full")
SOLAR_DEBOUNCE_S = 1.0               # gom các lần cảm biến đổi liên tiếp thành một bản tin
CLIMATE_DOMAIN = "climate"
MEDIA_DOMAIN = "media_player"        # loa / trình phát nhạc: thẻ màu tím, chạm để mở giao diện điều khiển
SUPPORTED_DOMAINS = TOGGLE_DOMAINS | ACTION_DOMAINS | SENSOR_DOMAINS | {WEATHER_DOMAIN, COVER_DOMAIN, CLIMATE_DOMAIN, MEDIA_DOMAIN, SOLAR_DOMAIN}

# Icon mặc định theo domain khi người dùng chưa chọn
DEFAULT_ICON = {
    "light": "mdi:lightbulb", "switch": "mdi:toggle-switch", "fan": "mdi:fan",
    "cover": "mdi:blinds", "lock": "mdi:lock", "scene": "mdi:play",
    "script": "mdi:play", "button": "mdi:gesture-tap-button",
    "sensor": "mdi:thermometer", "binary_sensor": "mdi:eye",
    "climate": "mdi:thermostat", "media_player": "mdi:speaker", "input_boolean": "mdi:toggle-switch",
    "automation": "mdi:cog", "weather": "mdi:weather-cloudy", "solar": "mdi:solar-power",
}

# Kiểu hiển thị của entity cover trên màn hình
COVER_STYLES = ("roller", "curtain_both", "curtain_left", "curtain_right")
CURTAIN_CLASSES = {"curtain", "blind", "shade", "awning"}   # device_class của rèm; còn lại coi là cửa cuốn
COVER_FEATURE_SET_POSITION = 4

# Độ rộng thẻ cảm biến trên màn hình: ×1 (mặc định), ×1.5, ×2
CARD_WIDTHS = (1, 1.5, 2)

# Đèn (light.*): giữ nhấn thẻ 3 giây trên màn hình để mở giao diện điều khiển độ sáng / màu / ngữ cảnh
LIGHT_DOMAIN = "light"
# Ngữ cảnh: id -> độ sáng %, màu. "hs" = (sắc độ, độ bão hoà) cho đèn RGB; "kelvin" = nhiệt độ màu (dùng cho đèn trắng / đèn không có RGB).
# Màn hình có bảng tên tương ứng (ui_light.cpp), sửa thì sửa cả hai nơi.
LIGHT_SCENES = {
    "reading": {"pct": 80, "kelvin": 5000},                       # Đọc sách: ánh sáng trắng
    "relax": {"pct": 40, "hs": (275, 100), "kelvin": 2700},       # Thư giãn: ánh sáng tím (đèn không có RGB: trắng ấm)
    "night": {"pct": 15, "hs": (48, 100), "kelvin": 2200},        # Đèn ngủ: ánh sáng vàng (đèn không có RGB: trắng ấm)
}
# Hiệu ứng: tự động tăng giảm độ sáng (do Home Assistant chạy). Dừng khi có bất kỳ lệnh nào khác lên đèn đó hoặc khi đèn tắt.
LIGHT_EFFECT = "effect"
LIGHT_EFFECT_MIN = 10          # độ sáng thấp nhất (%)
LIGHT_EFFECT_MAX = 100         # độ sáng cao nhất (%)
LIGHT_EFFECT_STEP = 10         # mỗi bước đổi bao nhiêu %
LIGHT_EFFECT_INTERVAL = 0.8    # giây giữa hai bước (cũng là thời gian chuyển mờ)
# Màu ánh sáng: id -> nhiệt độ màu K (Trắng ấm / Trung tính / Trắng lạnh)
LIGHT_COLORS = {"warm": 2700, "neutral": 4000, "cool": 6000}
