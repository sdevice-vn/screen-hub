/* Panel cấu hình Screen Hub: Tầng -> Phòng -> Thiết bị + chọn icon. Không cần build, chỉ JS thuần. */
const SUPPORTED = ["switch","light","fan","input_boolean","automation","lock","cover",
                   "scene","script","button","sensor","binary_sensor","climate","weather","media_player"];
const COVER_STYLES = [["roller", "Cửa cuốn"], ["curtain_both", "Rèm 2 bên"],
                      ["curtain_left", "Rèm 1 bên (đặt bên trái)"], ["curtain_right", "Rèm 1 bên (đặt bên phải)"]];
const SENSOR_DOMAINS = ["sensor", "binary_sensor"];
const SOLAR_STYLES = [["compact", "Thu nhỏ"], ["full", "Toàn màn hình"]];
const CARD_SIZES = SOLAR_STYLES;     // máy lạnh / rèm: Thu nhỏ (chạm để mở lớp phủ) hoặc Toàn màn hình
/* Cảm biến của Inverter: [role, nhãn, đơn vị gợi ý]. Role phải khớp ROLES trong solar.py. Công suất W/kW, sản lượng Wh/kWh... được tự đổi đơn vị. */
const SOLAR_GROUPS = [
  ["Dàn pin PV1", [["pv1_voltage", "Điện áp PV1", "V"], ["pv1_current", "Dòng điện PV1", "A"], ["pv1_power", "Công suất PV1", "W"]]],
  ["Dàn pin PV2 (nếu có)", [["pv2_voltage", "Điện áp PV2", "V"], ["pv2_current", "Dòng điện PV2", "A"], ["pv2_power", "Công suất PV2", "W"]]],
  ["Dàn pin PV3 (nếu có)", [["pv3_voltage", "Điện áp PV3", "V"], ["pv3_current", "Dòng điện PV3", "A"], ["pv3_power", "Công suất PV3", "W"]]],
  ["Pin lưu trữ", [["battery_voltage", "Điện áp pin", "V"], ["battery_soc", "Phần trăm pin", "%"],
                   ["battery_charge_power", "Công suất sạc", "W"], ["battery_discharge_power", "Công suất xả", "W"],
                   ["battery_charge_today", "Sạc hôm nay", "kWh"], ["battery_discharge_today", "Xả hôm nay", "kWh"]]],
  ["Lưới điện", [["grid_voltage", "Điện áp lưới", "V"], ["grid_import_power", "Công suất lấy lưới", "W"], ["grid_export_power", "Công suất đẩy lưới", "W"],
                    ["grid_import_today", "Lấy lưới hôm nay", "kWh"], ["grid_export_today", "Phát lưới hôm nay (tuỳ chọn)", "kWh"]]],
  ["Tải & cổng Backup", [["load_power", "Công suất tải", "W"], ["load_today", "Tải hôm nay", "kWh"],
                         ["backup_power", "Công suất cổng backup", "W"], ["backup_voltage", "Điện áp cổng backup", "V"]]],
  ["Khác", [["inverter_temp", "Nhiệt độ inverter", "°C"], ["yield_today", "Sản lượng PV hôm nay", "kWh"]]],
];
const ENERGY_STYLES = [["compact", "Thu nhỏ"], ["full", "Toàn màn hình"]];
const ENERGY_UNITS = ["Wh", "kWh", "MWh", "GWh"];
const SOLAR_TOTAL = SOLAR_GROUPS.reduce((n, g) => n + g[1].length, 0);
const WEATHER_STYLES = [["compact", "Thu nhỏ"], ["full", "Toàn màn hình"]];
const CARD_WIDTHS = [[1, "Thẻ ×1"], [1.5, "Thẻ ×1.5"], [2, "Thẻ ×2"]];
const CURTAIN_CLASSES = ["curtain", "blind", "shade", "awning"];
const fold = (t) => String(t).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");
const ic = (n) => `<ha-icon icon="mdi:${n}"></ha-icon>`;
const uid = () => Math.random().toString(36).slice(2, 9);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

class ScreenHubPanel extends HTMLElement {
  set hass(h) { this._hass = h; if (!this._init) { this._init = true; this._boot(); } }
  set narrow(v) { if (this._narrow !== v) { this._narrow = v; if (this.s) this._render(); } }
  set route(_) {} set panel(_) {}

  async _boot() {
    this.attachShadow({ mode: "open" });
    this.s = { entries: [], entry: null, layout: { floors: [] }, floor: 0, icons: [], dirty: false,
               picker: null, solarCfg: null, energyCfg: null, energyAll: false, msg: "" };
    this.s.icons = await this._hass.callWS({ type: "screen_hub/icons" });
    this.s.entries = await this._hass.callWS({ type: "screen_hub/list" });
    if (this.s.entries.length) await this._load(this.s.entries[0].entry_id);
    this._render();
  }

  async _load(entry_id) {
    const r = await this._hass.callWS({ type: "screen_hub/get", entry_id });
    this.s.entry = entry_id; this.s.layout = r.layout; this.s.floor = 0; this.s.dirty = false;
    this.s.layout.floors.forEach((f) => { f.rooms ||= []; f.rooms.forEach((r2) => r2.devices ||= []); });
  }

  async _save() {
    try {
      await this._hass.callWS({ type: "screen_hub/set", entry_id: this.s.entry, layout: this.s.layout });
      this.s.dirty = false; this.s.msg = "Đã lưu và gửi xuống màn hình ✔";
    } catch (e) { this.s.msg = "Lỗi: " + (e.message || e.code); }
    this._render();
  }

  _touch() { this.s.dirty = true; this.s.msg = ""; this._render(); }
  get _floor() { return this.s.layout.floors[this.s.floor]; }

  _defaultCover(eid) {
    const dc = this._hass.states[eid]?.attributes?.device_class;
    return CURTAIN_CLASSES.includes(dc) ? "curtain_both" : "roller";
  }

  _stateName(eid) { const st = this._hass.states[eid]; return st?.attributes?.friendly_name || eid; }

  /* Danh sách thực thể để gợi ý; "key" là chuỗi đã bỏ dấu để lọc không phân biệt dấu/hoa thường */
  _entityIndex() {
    return Object.keys(this._hass.states).filter((e) => SUPPORTED.includes(e.split(".")[0]))
      .map((e) => { const name = this._stateName(e); return { eid: e, name, key: fold(name + " " + e) }; })
      .sort((a, b) => a.name.localeCompare(b.name, "vi"));
  }

  _iconCell(name) {
    return `<ha-icon icon="${esc(name)}" style="--mdc-icon-size:26px"></ha-icon>`;
  }

  _render() {
    const s = this.s, f = this._floor;
    const html = `
    <style>
      :host{display:block;box-sizing:border-box;max-width:920px;margin:0 auto;padding:16px 16px 56px;overflow-x:hidden;
            color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif);
            --ctl:38px;--accent:var(--primary-color);--line:var(--divider-color);--bad:var(--error-color,#db4437)}
      *,*::before,*::after{box-sizing:border-box}
      [hidden]{display:none!important}
      ha-icon{--mdc-icon-size:20px;display:inline-flex}
      .hdr{display:flex;align-items:center;gap:6px;margin:-8px 0 2px -8px;font-size:20px;font-weight:500}
      .top{position:sticky;top:0;z-index:3;margin:0 -16px;padding:8px 16px;background:var(--primary-background-color)}
      .bar{display:flex;gap:10px;align-items:center}
      .bar select{flex:1 1 auto;max-width:340px;font-weight:500}
      button,input,select{font:inherit;font-size:14px;color:inherit}
      button{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:var(--ctl);padding:0 14px;
             border:1px solid var(--line);border-radius:10px;background:var(--card-background-color);cursor:pointer;
             transition:background .15s,border-color .15s,color .15s,transform .1s;-webkit-tap-highlight-color:transparent}
      button:hover:not(:disabled){background:var(--secondary-background-color)}
      button:active:not(:disabled){transform:scale(.96)}
      button:disabled{opacity:.35;cursor:default}
      button.save{min-width:72px;font-weight:500;background:var(--accent);border-color:var(--accent);
                  color:var(--text-primary-color,#fff);box-shadow:0 1px 3px #0003}
      button.save:hover:not(:disabled){background:var(--accent);filter:brightness(1.1)}
      button.save:disabled{background:var(--secondary-background-color);border-color:var(--line);
                           color:var(--secondary-text-color);box-shadow:none;opacity:1}
      input,select{height:var(--ctl);min-width:0;max-width:100%;padding:0 12px;border:1px solid var(--line);border-radius:10px;
                   background:var(--card-background-color);outline:none;transition:border-color .15s,box-shadow .15s}
      input:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 22%,transparent)}
      input::placeholder{color:var(--secondary-text-color);opacity:.8}
      .tabs{display:flex;gap:8px;margin:8px 0 14px;overflow-x:auto;scrollbar-width:none;padding:2px 2px 4px}
      .tabs::-webkit-scrollbar{display:none}
      .tab{flex:0 0 auto;height:34px;padding:0 16px;border-radius:999px}
      .tab.on{background:var(--accent);border-color:var(--accent);color:var(--text-primary-color,#fff);font-weight:500;box-shadow:0 1px 3px #0003}
      .tab.on:hover:not(:disabled){background:var(--accent)}
      .tab.add{border-style:dashed;color:var(--secondary-text-color)}
      .ftool,.rhead{display:flex;gap:8px;align-items:center}
      .grp{display:flex;gap:6px;flex:0 0 auto}
      .ib{width:var(--ctl);padding:0}
      .ib.pri{color:var(--accent)}
      .del:hover:not(:disabled){color:var(--bad);border-color:var(--bad);background:transparent}
      #floorName{flex:1 1 90px;font-size:15px;font-weight:500}
      .room{margin:14px 0;border:1px solid var(--line);border-radius:16px;background:var(--card-background-color);
            box-shadow:0 1px 3px #0000000f;overflow:hidden}
      .rhead{padding:12px}
      .roomName{flex:1 1 90px;padding:0 8px;font-size:16px;font-weight:500;border-color:transparent;background:transparent}
      .roomName:hover{border-color:var(--line)}
      .roomName:focus{background:var(--card-background-color)}
      .cnt{flex:0 0 auto;min-width:24px;height:24px;padding:0 8px;border-radius:12px;display:inline-flex;align-items:center;
           justify-content:center;font-size:12px;background:var(--secondary-background-color);color:var(--secondary-text-color)}
      .dev{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 12px;border-top:1px solid var(--line)}
      .dev:hover{background:color-mix(in srgb,var(--secondary-background-color) 45%,transparent)}
      .iconbtn{width:44px;height:44px;padding:0;border-radius:12px;background:var(--secondary-background-color)}
      .iconbtn ha-icon{--mdc-icon-size:26px}
      .dev .devName{flex:1 1 120px}
      .dev select{flex:1 1 160px;max-width:260px}
      .acts{display:flex;gap:2px;margin-left:auto}
      .acts button{width:34px;height:34px;padding:0;border-color:transparent;background:transparent}
      .acts button:hover:not(:disabled){border-color:var(--line)}
      .acts .delDev:hover:not(:disabled){color:var(--bad);border-color:var(--bad)}
      .empty{padding:14px 16px;border-top:1px solid var(--line);font-size:13px;color:var(--secondary-text-color)}
      .empty.big{margin:14px 0;padding:32px 16px;text-align:center;border:1px dashed var(--line);border-radius:16px}
      .addWrap{padding:10px 12px 12px;border-top:1px solid var(--line);background:color-mix(in srgb,var(--secondary-background-color) 40%,transparent)}
      .addRow{display:flex;gap:8px;flex-wrap:wrap}
      .addEntity{flex:0 1 260px;min-width:0}
      .addRow button{flex:0 0 auto}
      .sol{display:flex;align-items:center;gap:8px;flex:1 1 150px;max-width:260px}
      .sol .cfg{height:34px;padding:0 12px;border-radius:10px}
      .sol .cnt2{font-size:12px;color:var(--secondary-text-color);white-space:nowrap}
      .srow{display:grid;grid-template-columns:minmax(120px,170px) 1fr;gap:8px;align-items:center;padding:4px 0}
      .srow label{font-size:13px}
      .srow label small{display:block;opacity:.55;font-size:11px}
      .srow input{width:100%}
      .shint{margin:10px 0 2px;font-size:12px;color:var(--secondary-text-color);line-height:1.5}
      .sugg{margin-top:8px;max-height:260px;overflow:auto;overscroll-behavior:contain;border:1px solid var(--line);
            border-radius:12px;background:var(--card-background-color);box-shadow:0 4px 14px #0000001f}
      .opt{display:flex;flex-direction:column;gap:2px;justify-content:center;min-height:46px;padding:8px 14px;cursor:pointer;border-top:1px solid var(--line)}
      .opt:first-child{border-top:0}
      .opt:hover,.opt:active{background:var(--secondary-background-color)}
      .oname{font-size:14px}
      .oeid{font-size:12px;opacity:.6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .none{padding:12px 14px;font-size:13px;opacity:.6}
      .modal{position:fixed;inset:0;z-index:9;display:flex;align-items:center;justify-content:center;background:#0008;backdrop-filter:blur(2px)}
      .sheet{width:min(760px,94vw);max-height:85vh;overflow:auto;overscroll-behavior:contain;border-radius:16px;
             background:var(--card-background-color);box-shadow:0 12px 40px #0006}
      .shead{position:sticky;top:0;z-index:1;display:flex;gap:8px;align-items:center;padding:12px 16px;
             background:var(--card-background-color);border-bottom:1px solid var(--line)}
      .shead b{flex:0 0 auto;font-size:16px}
      .shead input{flex:1 1 120px}
      .sbody{padding:4px 16px 16px}
      .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(52px,1fr));gap:6px}
      .grid button{height:48px;padding:0}
      h3{margin:14px 0 6px;font-size:12px;font-weight:500;letter-spacing:.05em;text-transform:uppercase;color:var(--secondary-text-color)}
      .toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10;max-width:90vw;padding:10px 18px;
             border-radius:12px;font-size:14px;background:var(--primary-text-color);color:var(--card-background-color);
             box-shadow:0 4px 16px #0005;animation:up .2s}
      .toast.err{background:var(--bad);color:#fff}
      @keyframes up{from{opacity:0;transform:translate(-50%,8px)}}
      @media (max-width:600px){
        :host{padding:8px 10px 56px;--ctl:42px}
        .top{margin:0 -10px;padding:6px 10px}
        input,select{font-size:16px}            /* tránh trình duyệt di động tự phóng to khi chạm vào ô nhập */
        .bar select{max-width:none}
        .addEntity{flex:1 1 100%}                 /* ô nhập một hàng riêng, các nút Thêm / Inverter / Biểu đồ ĐNTT xuống hàng dưới */
        .addRow button{flex:1 1 auto}
        .lbl{display:none}
        .del{width:var(--ctl);padding:0}
        .dev select{order:3;flex:1 1 100%;max-width:none}   /* ô chọn kiểu/độ rộng xuống dòng riêng, nút ▲▼✕ giữ ở hàng đầu */
        .acts button{width:36px;height:36px}
        .sheet{width:100vw;height:100vh;max-height:100vh;border-radius:0}
        .toast{bottom:16px}
      }
    </style>
    ${s.entries.length ? "" : "<p>Chưa có màn hình nào. Vào Cài đặt → Thiết bị &amp; dịch vụ để thêm Screen Hub.</p>"}
    ${this._narrow ? `<div class="hdr"><ha-menu-button></ha-menu-button><b>Màn hình HA</b></div>` : ""}
    <div class="top">
      <div class="bar">
        <select id="entry">${s.entries.map((e) => `<option value="${e.entry_id}" ${e.entry_id === s.entry ? "selected" : ""}>${esc(e.title)}</option>`).join("")}</select>
        <button class="save" id="save" title="Lưu &amp; gửi xuống màn hình" ${s.dirty ? "" : "disabled"}>Lưu</button>
      </div>
    </div>
    <div class="tabs">
      ${s.layout.floors.map((fl, i) => `<button data-floor="${i}" class="tab ${i === s.floor ? "on" : ""}">${esc(fl.name)}</button>`).join("")}
      <button id="addFloor" class="tab add">${ic("plus")}<span>Thêm tầng</span></button>
    </div>
    ${f ? `
    <div class="ftool">
      <input id="floorName" value="${esc(f.name)}" maxlength="24" placeholder="Tên tầng">
      <div class="grp">
        <button class="ib" id="fUp" title="Chuyển tầng sang trái" ${s.floor === 0 ? "disabled" : ""}>${ic("chevron-left")}</button>
        <button class="ib" id="fDown" title="Chuyển tầng sang phải" ${s.floor === s.layout.floors.length - 1 ? "disabled" : ""}>${ic("chevron-right")}</button>
        <button class="ib pri" id="addRoom" title="Thêm phòng" aria-label="Thêm phòng">${ic("plus")}</button>
        <button class="del" id="delFloor" title="Xóa tầng">${ic("delete-outline")}<span class="lbl">Xóa tầng</span></button>
      </div>
    </div>
    ${f.rooms.map((r, ri) => `
      <div class="room" data-room="${ri}">
        <div class="rhead">
          <input class="roomName" value="${esc(r.name)}" maxlength="24" placeholder="Tên phòng">
          <span class="cnt" title="Số thiết bị">${r.devices.length}</span>
          <div class="grp">
            <button class="ib rUp" title="Chuyển phòng lên" ${ri === 0 ? "disabled" : ""}>${ic("arrow-up")}</button>
            <button class="ib rDown" title="Chuyển phòng xuống" ${ri === f.rooms.length - 1 ? "disabled" : ""}>${ic("arrow-down")}</button>
            <button class="del delRoom" title="Xóa phòng">${ic("delete-outline")}<span class="lbl">Xóa phòng</span></button>
          </div>
        </div>
        ${r.devices.length ? "" : `<div class="empty">Chưa có thiết bị. Gõ tên thiết bị ở ô bên dưới để thêm.</div>`}
        ${r.devices.map((d, di) => `
          <div class="dev" data-dev="${di}">
            <button class="iconbtn pickIcon" title="Chọn icon">${this._iconCell(d.icon || "mdi:help-circle-outline")}</button>
            <input class="devName" value="${esc(d.name)}" maxlength="24" title="${esc(d.entity_id)}" placeholder="${esc(d.entity_id.startsWith("solar.") ? "Hệ thống NLMT" : d.entity_id.startsWith("energy.") ? "Biểu đồ ĐNTT" : this._stateName(d.entity_id))}">
            ${d.entity_id.startsWith("cover.") ? `<select class="coverStyle" title="Kiểu hiển thị trên màn hình">${COVER_STYLES.map(([v, t]) =>
              `<option value="${v}" ${(d.cover_style || this._defaultCover(d.entity_id)) === v ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
            ${d.entity_id.startsWith("cover.") ? `<select class="coverSize" title="Thẻ trên màn hình: thu nhỏ (chạm để mở) hoặc toàn màn hình">${CARD_SIZES.map(([v, t]) =>
              `<option value="${v}" ${(d.cover_size || "full") === v ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
            ${d.entity_id.startsWith("climate.") ? `<select class="climateStyle" title="Thẻ trên màn hình: thu nhỏ (chạm để mở) hoặc toàn màn hình">${CARD_SIZES.map(([v, t]) =>
              `<option value="${v}" ${(d.climate_style || "full") === v ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
            ${d.entity_id.startsWith("weather.") ? `<select class="weatherStyle" title="Kiểu hiển thị trên màn hình">${WEATHER_STYLES.map(([v, t]) =>
              `<option value="${v}" ${(d.weather_style || "compact") === v ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
            ${d.entity_id.startsWith("solar.") ? `<select class="solarStyle" title="Kiểu hiển thị trên màn hình">${SOLAR_STYLES.map(([v, t]) =>
              `<option value="${v}" ${(d.solar_style || "compact") === v ? "selected" : ""}>${t}</option>`).join("")}</select>
              <span class="sol"><button class="cfg solarCfg" title="Chọn các cảm biến của Inverter">${ic("cog-outline")}<span>Cảm biến</span></button>
              <span class="cnt2">${Object.values(d.sensors || {}).filter(Boolean).length}/${SOLAR_TOTAL}</span></span>` : ""}
            ${d.entity_id.startsWith("energy.") ? `<select class="energyStyle" title="Kiểu hiển thị trên màn hình">${ENERGY_STYLES.map(([v, t]) =>
              `<option value="${v}" ${(d.energy_style || "compact") === v ? "selected" : ""}>${t}</option>`).join("")}</select>
              <span class="sol"><button class="cfg energyCfg" title="Chọn cảm biến điện năng cộng dồn">${ic("cog-outline")}<span>Cảm biến</span></button>
              <span class="cnt2" title="${esc(d.energy_sensor || "")}">${d.energy_sensor ? "✔ " + esc(this._stateName(d.energy_sensor)) : "Chưa chọn"}</span></span>` : ""}
            ${SENSOR_DOMAINS.includes(d.entity_id.split(".")[0]) ? `<select class="devWidth" title="Độ rộng thẻ trên màn hình">${CARD_WIDTHS.map(([v, t]) =>
              `<option value="${v}" ${(d.width || 1) === v ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
            <div class="acts">
              <button class="dUp" title="Lên" ${di === 0 ? "disabled" : ""}>${ic("arrow-up")}</button>
              <button class="dDown" title="Xuống" ${di === r.devices.length - 1 ? "disabled" : ""}>${ic("arrow-down")}</button>
              <button class="delDev" title="Xóa thiết bị">${ic("close")}</button>
            </div>
          </div>`).join("")}
        <div class="addWrap">
          <div class="addRow">
            <input class="addEntity" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Gõ tên thiết bị để thêm…">
            <button class="addDev">${ic("plus")}<span>Thêm</span></button>
            <button class="addSolar" title="Thêm thẻ giám sát hệ thống năng lượng mặt trời (Inverter)">${ic("plus")}<span>Inverter</span></button>
            <button class="addEnergy" title="Thêm biểu đồ điện năng tiêu thụ từng ngày trong tháng">${ic("plus")}<span>Biểu đồ ĐNTT</span></button>
          </div>
          <div class="sugg" hidden></div>
        </div>
      </div>`).join("")}
    ${f.rooms.length ? "" : `<div class="empty big">Tầng này chưa có phòng. Nhấn nút + để thêm phòng.</div>`}` : (s.entries.length ? `<div class="empty big">Chưa có tầng nào. Nhấn "Thêm tầng" để bắt đầu.</div>` : "")}
    ${s.msg ? `<div class="toast ${/^(Lỗi|Chọn)/.test(s.msg) ? "err" : ""}">${esc(s.msg)}</div>` : ""}
    ${s.picker ? this._pickerHtml() : ""}
    ${s.solarCfg ? this._solarHtml() : ""}
    ${s.energyCfg ? this._energyHtml() : ""}`;
    this.shadowRoot.innerHTML = html;
    clearTimeout(this._tm);
    if (s.msg) this._tm = setTimeout(() => { s.msg = ""; this.shadowRoot.querySelector(".toast")?.remove(); }, 3500);
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) { menu.hass = this._hass; menu.narrow = this._narrow; }    // mở thanh bên của HA trên điện thoại
    this._bind();
  }

  _solarHtml() {
    const d = this.s.solarCfg, m = d.sensors || {};
    const opts = Object.keys(this._hass.states).filter((e) => /^(sensor|input_number|number)\./.test(e))
      .map((e) => `<option value="${esc(e)}">${esc(this._stateName(e))}</option>`).join("");
    return `<div class="modal" id="solarModal"><div class="sheet">
      <div class="shead"><b>Cảm biến Inverter</b><span style="flex:1"></span><button class="ib" id="closeSolar" title="Đóng">${ic("close")}</button></div>
      <div class="sbody">
        <datalist id="sensorList">${opts}</datalist>
        <div class="shint">Chọn cảm biến HA cho từng thông số (gõ tên hoặc entity_id). Ô nào không có thì để trống. Đơn vị W/kW, Wh/kWh, mV/V… được tự quy đổi.
          Hệ thống có tối đa 3 string PV; string nào không khai báo cảm biến sẽ không hiển thị.</div>
        ${SOLAR_GROUPS.map(([title, rows]) => `<h3>${esc(title)}</h3>${rows.map(([role, label, unit]) => `
          <div class="srow"><label>${esc(label)}<small>${esc(unit)}</small></label>
            <input data-role="${role}" list="sensorList" value="${esc(m[role] || "")}" autocomplete="off" autocapitalize="off" spellcheck="false"
              placeholder="sensor.…"></div>`).join("")}`).join("")}
      </div></div></div>`;
  }

  /* Cảm biến điện năng cộng dồn: ưu tiên device_class "energy" hoặc đơn vị Wh/kWh/MWh; có nút "Hiện tất cả cảm biến" */
  _energyCandidates(q) {
    const toks = fold(q || "").split(/\s+/).filter(Boolean), all = this.s.energyAll;
    return Object.keys(this._hass.states).filter((e) => e.startsWith("sensor."))
      .filter((e) => { const a = this._hass.states[e].attributes || {};
        return all || a.device_class === "energy" || ENERGY_UNITS.includes(a.unit_of_measurement); })
      .map((e) => { const name = this._stateName(e); return { eid: e, name, key: fold(name + " " + e) }; })
      .filter((o) => toks.every((t) => o.key.includes(t)))
      .sort((a, b) => a.name.localeCompare(b.name, "vi"));
  }

  _energySuggHtml(q) {
    const list = this._energyCandidates(q);
    return list.length ? list.slice(0, 40).map((o) => { const st = this._hass.states[o.eid];
      return `<div class="opt" data-eid="${esc(o.eid)}"><span class="oname">${esc(o.name)}</span><span class="oeid">${esc(o.eid)} · ${esc(st.state)} ${esc(st.attributes.unit_of_measurement || "")}</span></div>`; }).join("")
      : `<div class="none">Không có cảm biến phù hợp${this.s.energyAll ? "" : " (nhấn \"Hiện tất cả cảm biến\")"}</div>`;
  }

  _energyHtml() {
    const d = this.s.energyCfg, cur = d.energy_sensor, st = cur && this._hass.states[cur];
    return `<div class="modal" id="energyModal"><div class="sheet">
      <div class="shead"><b>Cảm biến điện năng</b><span style="flex:1"></span><button class="ib" id="closeEnergy" title="Đóng">${ic("close")}</button></div>
      <div class="sbody">
        <div class="shint">Chọn <b>một</b> cảm biến điện năng <b>cộng dồn</b> (kWh, Wh, MWh…). Hệ thống tự tính mức tiêu thụ từng ngày bằng hiệu giữa các lần đọc rồi lưu lại,
          nên biểu đồ chỉ có số liệu từ lúc chọn cảm biến. Đơn vị Wh/kWh/MWh được tự quy đổi; cảm biến bị reset về 0 cũng được xử lý.</div>
        <h3>Đang chọn</h3>
        <div class="srow" style="grid-template-columns:1fr auto">
          <div>${cur ? `<b>${esc(this._stateName(cur))}</b><small style="display:block;opacity:.6">${esc(cur)}${st ? " · " + esc(st.state) + " " + esc(st.attributes.unit_of_measurement || "") : " · không tìm thấy trong HA"}</small>` : `<span style="opacity:.6">Chưa chọn cảm biến</span>`}</div>
          ${cur ? `<button class="ib del" id="energyClear" title="Bỏ chọn">${ic("close")}</button>` : ""}
        </div>
        <h3>Tìm cảm biến</h3>
        <div class="addRow"><input id="energyQ" style="flex:1 1 200px" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Gõ tên hoặc entity_id…">
          <button id="energyAll">${this.s.energyAll ? "Chỉ cảm biến điện năng" : "Hiện tất cả cảm biến"}</button></div>
        <div class="sugg" id="energySugg">${this._energySuggHtml("")}</div>
      </div></div></div>`;
  }

  _pickerHtml() {
    const cats = {};
    this.s.icons.forEach((i) => (cats[i.cat] ||= []).push(i));
    return `<div class="modal" id="modal"><div class="sheet">
      <div class="shead"><b>Chọn icon</b><input id="iconQ" placeholder="Tìm icon…" autocomplete="off" autocapitalize="off" spellcheck="false">
        <button id="noIcon">Mặc định</button><button class="ib" id="closePick" title="Đóng">${ic("close")}</button></div>
      <div class="sbody">${Object.entries(cats).map(([c, list]) => `<div class="cat"><h3>${esc(c)}</h3><div class="grid">
        ${list.map((i) => `<button data-icon="${i.name}" title="${i.name.slice(4)}">${this._iconCell(i.name)}</button>`).join("")}
      </div></div>`).join("")}</div></div></div>`;
  }

  _bind() {
    const q = (sel) => this.shadowRoot.querySelector(sel);
    const all = (sel) => [...this.shadowRoot.querySelectorAll(sel)];
    const L = this.s.layout, f = this._floor;
    const move = (arr, i, d) => { const j = i + d; [arr[i], arr[j]] = [arr[j], arr[i]]; };

    q("#entry")?.addEventListener("change", async (e) => { await this._load(e.target.value); this._render(); });
    q("#save")?.addEventListener("click", () => this._save());
    all("[data-floor]").forEach((b) => b.addEventListener("click", () => { this.s.floor = +b.dataset.floor; this._render(); }));
    q("#addFloor")?.addEventListener("click", () => {
      L.floors.push({ id: uid(), name: `Tầng ${L.floors.length + 1}`, rooms: [] });
      this.s.floor = L.floors.length - 1; this._touch(); });
    if (!f) return;
    q("#floorName")?.addEventListener("change", (e) => { f.name = e.target.value.trim() || f.name; this._touch(); });
    q("#fUp")?.addEventListener("click", () => { move(L.floors, this.s.floor, -1); this.s.floor--; this._touch(); });
    q("#fDown")?.addEventListener("click", () => { move(L.floors, this.s.floor, 1); this.s.floor++; this._touch(); });
    q("#delFloor")?.addEventListener("click", () => {
      if (!confirm(`Xóa "${f.name}" và toàn bộ phòng/thiết bị trong tầng?`)) return;
      L.floors.splice(this.s.floor, 1); this.s.floor = Math.max(0, this.s.floor - 1); this._touch(); });
    q("#addRoom")?.addEventListener("click", () => {
      f.rooms.push({ id: uid(), name: `Phòng ${f.rooms.length + 1}`, devices: [] }); this._touch(); });

    all(".room").forEach((el) => {
      const r = f.rooms[+el.dataset.room], ri = +el.dataset.room;
      el.querySelector(".roomName").addEventListener("change", (e) => { r.name = e.target.value.trim() || r.name; this._touch(); });
      el.querySelector(".rUp").addEventListener("click", () => { move(f.rooms, ri, -1); this._touch(); });
      el.querySelector(".rDown").addEventListener("click", () => { move(f.rooms, ri, 1); this._touch(); });
      el.querySelector(".delRoom").addEventListener("click", () => {
        if (confirm(`Xóa phòng "${r.name}"?`)) { f.rooms.splice(ri, 1); this._touch(); } });
      const inp = el.querySelector(".addEntity"), box = el.querySelector(".sugg");
      const used = new Set(r.devices.map((d) => d.entity_id));
      const matches = () => {
        const toks = fold(inp.value).split(/\s+/).filter(Boolean);
        return this._entityIndex().filter((o) => !used.has(o.eid) && toks.every((t) => o.key.includes(t)));
      };
      const showSugg = () => {
        const list = matches();
        box.innerHTML = list.length
          ? list.slice(0, 40).map((o) => `<div class="opt" data-eid="${esc(o.eid)}"><span class="oname">${esc(o.name)}</span><span class="oeid">${esc(o.eid)}</span></div>`).join("")
          : `<div class="none">Không có thiết bị phù hợp</div>`;
        box.hidden = false;
      };
      const addEid = (eid) => {
        if (!this._hass.states[eid] || !SUPPORTED.includes(eid.split(".")[0])) { this.s.msg = "Chọn thiết bị trong danh sách gợi ý"; this._render(); return; }
        const dev = { entity_id: eid, name: "", icon: "" };
        if (eid.startsWith("cover.")) dev.cover_style = this._defaultCover(eid);
        if (eid.startsWith("weather.")) dev.weather_style = "compact";
        if (eid.startsWith("cover.")) dev.cover_size = "compact";
        if (eid.startsWith("climate.")) dev.climate_style = "compact";
        r.devices.push(dev); this._touch(); };
      const add = () => {          // nút "＋ Thêm" / phím Enter: nhập đúng entity_id hoặc chỉ còn 1 gợi ý (Enter: lấy gợi ý đầu)
        const typed = inp.value.trim().toLowerCase(), list = matches();
        addEid(this._hass.states[typed] ? typed : list.length ? list[0].eid : typed); };
      inp.addEventListener("focus", () => { showSugg(); setTimeout(() => inp.scrollIntoView({ block: "center", behavior: "smooth" }), 300); });
      inp.addEventListener("input", showSugg);
      inp.addEventListener("blur", () => setTimeout(() => { box.hidden = true; }, 150));
      box.addEventListener("mousedown", (e) => e.preventDefault());     // giữ focus ở ô nhập khi chạm vào danh sách
      box.addEventListener("click", (e) => { const o = e.target.closest(".opt"); if (o) addEid(o.dataset.eid); });
      el.querySelector(".addDev").addEventListener("click", add);
      el.querySelector(".addSolar").addEventListener("click", () => {        // thiết bị ảo: không có entity trong HA, cảm biến chọn ở thẻ riêng
        const dev = { entity_id: "solar." + uid(), name: "Hệ thống NLMT", icon: "mdi:solar-power", solar_style: "compact", sensors: {} };
        r.devices.push(dev); this.s.solarCfg = dev; this._touch(); });
      el.querySelector(".addEnergy").addEventListener("click", () => {       // thiết bị ảo: cảm biến chọn ở thẻ riêng
        const dev = { entity_id: "energy." + uid(), name: "Biểu đồ ĐNTT", icon: "mdi:meter-electric", energy_style: "compact", energy_sensor: "" };
        r.devices.push(dev); this.s.energyAll = false; this.s.energyCfg = dev; this._touch(); });
      inp.addEventListener("keydown", (e) => e.key === "Enter" && add());
      el.querySelectorAll(".dev").forEach((de) => {
        const di = +de.dataset.dev, d = r.devices[di];
        de.querySelector(".devName").addEventListener("change", (e) => { d.name = e.target.value.trim(); this._touch(); });
        de.querySelector(".devWidth")?.addEventListener("change", (e) => { d.width = parseFloat(e.target.value); this._touch(); });
        de.querySelector(".energyStyle")?.addEventListener("change", (e) => { d.energy_style = e.target.value; this._touch(); });
        de.querySelector(".energyCfg")?.addEventListener("click", () => { this.s.energyAll = false; this.s.energyCfg = d; this._render(); });
        de.querySelector(".solarStyle")?.addEventListener("change", (e) => { d.solar_style = e.target.value; this._touch(); });
        de.querySelector(".solarCfg")?.addEventListener("click", () => { this.s.solarCfg = d; this._render(); });
        de.querySelector(".weatherStyle")?.addEventListener("change", (e) => { d.weather_style = e.target.value; this._touch(); });
        de.querySelector(".coverStyle")?.addEventListener("change", (e) => { d.cover_style = e.target.value; this._touch(); });
        de.querySelector(".coverSize")?.addEventListener("change", (e) => { d.cover_size = e.target.value; this._touch(); });
        de.querySelector(".climateStyle")?.addEventListener("change", (e) => { d.climate_style = e.target.value; this._touch(); });
        de.querySelector(".dUp").addEventListener("click", () => { move(r.devices, di, -1); this._touch(); });
        de.querySelector(".dDown").addEventListener("click", () => { move(r.devices, di, 1); this._touch(); });
        de.querySelector(".delDev").addEventListener("click", () => { r.devices.splice(di, 1); this._touch(); });
        de.querySelector(".pickIcon").addEventListener("click", () => { this.s.picker = d; this._render(); });
      });
    });

    const closeSolar = () => { this.s.solarCfg = null; this._render(); };
    q("#closeSolar")?.addEventListener("click", closeSolar);
    q("#solarModal")?.addEventListener("click", (e) => { if (e.target.id === "solarModal") closeSolar(); });
    all("[data-role]").forEach((inp) => inp.addEventListener("change", () => {
      const d = this.s.solarCfg; d.sensors ||= {};
      const v = inp.value.trim().toLowerCase();
      if (v) d.sensors[inp.dataset.role] = v; else delete d.sensors[inp.dataset.role];
      this.s.dirty = true;
      this.shadowRoot.querySelector("#save")?.removeAttribute("disabled");   // không dựng lại giao diện để khỏi mất tiêu điểm ô nhập
    }));
    const closeEnergy = () => { this.s.energyCfg = null; this._render(); };
    q("#closeEnergy")?.addEventListener("click", closeEnergy);
    q("#energyModal")?.addEventListener("click", (e) => { if (e.target.id === "energyModal") closeEnergy(); });
    q("#energyClear")?.addEventListener("click", () => { this.s.energyCfg.energy_sensor = ""; this._touch(); });
    const eq = q("#energyQ"), esg = q("#energySugg");
    if (eq) {
      eq.addEventListener("input", () => { esg.innerHTML = this._energySuggHtml(eq.value); });
      q("#energyAll").addEventListener("click", () => { this.s.energyAll = !this.s.energyAll; this._render(); });
      esg.addEventListener("click", (e) => { const o = e.target.closest(".opt"); if (!o) return;
        this.s.energyCfg.energy_sensor = o.dataset.eid; this.s.energyCfg = null; this._touch(); });
    }
    const closePick = () => { this.s.picker = null; this._render(); };
    q("#closePick")?.addEventListener("click", closePick);
    q("#modal")?.addEventListener("click", (e) => { if (e.target.id === "modal") closePick(); });
    const iq = q("#iconQ");
    iq?.addEventListener("input", () => {      // lọc icon theo tên, ẩn nhóm không còn icon nào
      const t = fold(iq.value).trim();
      all("[data-icon]").forEach((b) => { b.hidden = !!t && !fold(b.title).includes(t); });
      all(".cat").forEach((c) => { c.hidden = !c.querySelector("[data-icon]:not([hidden])"); });
    });
    q("#noIcon")?.addEventListener("click", () => { this.s.picker.icon = ""; this.s.picker = null; this._touch(); });
    all("[data-icon]").forEach((b) => b.addEventListener("click", () => {
      this.s.picker.icon = b.dataset.icon; this.s.picker = null; this._touch(); }));
  }
}
customElements.define("screen-hub-panel", ScreenHubPanel);
