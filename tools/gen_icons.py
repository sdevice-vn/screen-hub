#!/usr/bin/env python3
"""Tạo mdi_icons.json (danh sách icon cho panel HA) từ @mdi/font.
Chạy (ở thư mục gốc repo): python3 tools/gen_icons.py <materialdesignicons.css>
Thêm/bớt icon: sửa CATEGORIES rồi chạy lại."""
import json, re, sys

CATEGORIES = {
 "Chiếu sáng": "lightbulb lightbulb-outline lightbulb-group ceiling-light ceiling-light-outline floor-lamp lamp desk-lamp wall-sconce wall-sconce-flat led-strip led-strip-variant spotlight spotlight-beam light-switch lightbulb-on lightbulb-off string-lights chandelier",
 "Ổ cắm & điện": "power power-plug power-socket power-socket-eu power-socket-us flash lightning-bolt battery battery-charging solar-panel solar-power ev-station transmission-tower meter-electric current-ac",
 "Công tắc": "toggle-switch toggle-switch-off light-switch-off gesture-tap-button radiobox-marked button-pointer",
 "Quạt & điều hòa": "fan fan-off air-conditioner air-filter air-purifier hvac heat-wave snowflake thermostat radiator radiator-off sun-thermometer coolant-temperature",
 "Cửa & rèm": "door door-open door-closed garage garage-open gate window-closed window-open blinds blinds-open curtains curtains-closed roller-shade roller-shade-closed lock lock-open-variant key-variant",
 "Cảm biến": "thermometer thermometer-high thermometer-low water-percent water-thermometer gauge molecule-co2 smoke-detector smoke-detector-variant motion-sensor eye human-greeting-variant run walk radar leak flood weather-windy brightness-5 brightness-6 weather-sunny weather-night weather-cloudy weather-rainy",
 "An ninh": "shield-home shield-lock shield-check cctv camera doorbell bell bell-ring alarm-light alert siren fire fire-alert",
 "Phòng": "home home-outline sofa bed bed-double bed-king desk silverware-fork-knife stove countertop-fire fridge fridge-outline microwave toilet shower bathtub washing-machine dryer television television-ambient-light stairs balcony garage-variant pine-tree flower-outline sprinkler sprinkler-variant",
 "Thiết bị": "television speaker speaker-wireless music cast robot-vacuum robot-mower coffee-maker kettle water-boiler rice-cooker dishwasher iron lock-smart router-wireless router-network wifi cellphone laptop printer-3d garage-alert water-pump water-pump-off water-heater pool hot-tub car car-electric ev-plug-type2 scooter",
 "Cảnh & hành động": "play pause stop movie-open movie-roll-outline weather-night sunglasses sleep sleep-off exit-run home-export-outline home-import-outline account-group shield-moon bed-clock party-popper silverware-variant script-text-play rocket-launch",
 "Khác": "star heart bookmark flag tag information help-circle plus minus check close cog refresh clock-outline calendar timer-outline bolt cloud map-marker",
}

css = open(sys.argv[1], encoding="utf-8").read()
cp = {m.group(1): int(m.group(2), 16)
      for m in re.finditer(r'\.mdi-([a-z0-9-]+)::before\s*\{\s*content:\s*"\\([0-9A-Fa-f]+)"', css)}

icons, seen, missing = [], set(), []
for cat, names in CATEGORIES.items():
    for n in names.split():
        if n in seen: continue
        seen.add(n)
        if n not in cp: missing.append(n); continue
        icons.append({"name": f"mdi:{n}", "cp": cp[n], "cat": cat})

json.dump({"version": 1, "icons": icons}, open("custom_components/screen_hub/mdi_icons.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"{len(icons)} icon OK; thiếu trong MDI: {missing}")
