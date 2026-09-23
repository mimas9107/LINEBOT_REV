# 任務清單：LINEBOT_REV trachecker（臺鐵）插件（rev2.6.0）

> 依據 `PLAN.md`（2026-09-23 草案）拆解為可執行的原子任務，每項可獨立驗證
> 決策定案：D1 sys.path 注入 trachecker / D2 暴露 5 支（藏 resolve_tra_station）全 READ_ONLY / D3 dispatch adapter lambda / D4 rev2.6.0 / D5 話術透傳 / D6 沿用 __main__ 自檢

---

## 階段 1：tra 插件檔

### 1.1 建立 `services/plugins/tra.py`
- [ ] `sys.path.append(Path(__file__).resolve().parents[3] / "trachecker")` 後 `from trachecker.agent_tools import TOOLS as TRACHECKER_TOOLS, dispatch`
- [ ] `REQUIRED_ENV = ["TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]`
- [ ] `TOOLS = [...]`：**5 支**全部註冊（`search_tra_od_timetable` / `get_tra_station_live_board` / `get_tra_train_live_board` / `get_tra_fare_v2_estimate` / `get_tra_itinerary`，**排除 primitive `resolve_tra_station`**），schema 沿用 trachecker 的 `{name, description, parameters}`，handler 用 `lambda _n=_name, **_kw: dispatch(_n, _kw)`，每支掛 `"policy": {"risk": "READ_ONLY"}`
- [ ] 版本頭 `版本: rev2.6.0`

### 1.2 smoke：registry 完整性
- [ ] `import services.plugins` 不報錯、無 duplicate tool name
- [ ] `ENABLED_PLUGINS=tra` + TDX env 補齊 → `TOOLS` 含 5 支、`DISPATCH` 5 鍵、`POLICY` 5 鍵皆 READ_ONLY
- [ ] 缺 `TDX_CLIENT_SECRET` → tra 插件跳過、其餘插件不受影響
- [ ] trachecker 目錄不存在 → plugin 靜默跳過，應用不崩潰

---

## 階段 2：環境與文件

### 2.1 `.env.example`
- [ ] `ENABLED_PLUGINS=weather,hackmd,tra`；註記 tra 與 weather 共用 TDX env，不新增欄位

### 2.2 README
- [ ] 啟用插件工具清單新增 tra 5 支（名稱 / 用途 / 全 READ_ONLY）
- [ ] 註記 tra 查詢僅執行 TDX；票價為 TDX v2 估算、以官方為準；itinerary 無直達需拆段

### 2.3 CHANGELOG / MEMOIR
- [ ] CHANGELOG 新增 `[2.6.0]` 條目（保留 [2.5.0]，描述 tra 插件整合）
- [ ] MEMOIR 紀錄 D1-D6 決策與風險（parents[3] 路徑依賴）

### 2.4 版本字串同步 2.5.0 → 2.6.0
- [ ] 全部 .py 版本頭 + app.py runtime 字串 → 2.6.0
- [ ] 四份文件 project_version → 2.6.0
- [ ] 跑版本同步檢查（`version-sync-checker`）全綠

---

## 階段 3：實機驗證（需使用者 Render 部署後回報）

### 3.1 功能測試
- [ ] `ai: 從台北到台中的票價` → `get_tra_fare_v2_estimate`，話術含「實際票價以官方為準」
- [ ] `ai: 板橋接下來有什麼車` → `get_tra_station_live_board`
- [ ] `ai: 查 125 車次現況` → `get_tra_train_live_board`
- [ ] `ai: 新竹到台中怎麼搭` → `get_tra_itinerary`，回傳方案與排序
- [ ] `ai: 台北到台中的時刻表` → `search_tra_od_timetable`

### 3.2 穩定性
- [ ] tra + weather 同時載入共用 TDX env，無衝突
- [ ] 群組/聊天室使用 tra 查詢正常（READ_ONLY 人人可用）
- [ ] tool 回應時間 < 10 秒、結果大小合理（不洩漏 TDX token）

---

## 完成定義

- [ ] 所有 P0 任務勾選完成
- [ ] 部署到 Render，tra 5 支工具皆可用
- [ ] 5 支工具功能實測正確回應（3.1）
- [ ] 更新 `CHANGELOG.md`、`README.md`、`MEMOIR.md` 版本號（2.5.0 → 2.6.0）與內容（SPEC 依 D6 機制化不動）