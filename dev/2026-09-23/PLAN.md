# 實作計畫（草案）：LINEBOT_REV trachecker（臺鐵）插件整合

> 依據 `trachecker`（TRA Checker）前驅專案 dev/2026-09-21 HANDOFF 的 next step：
> `research/linebot-rev-integration-plan.md`（TASK-008，on-hold）已於前驅專案完成 7/7 官方票價交叉驗證後解鎖，
> 本輪於 LINEBOT_REV 落地 `services/plugins/tra.py`。

## 前驅專案現況（trachecker 0.4.0，dev/2026-09-21 CLOSE 待確認）

- **本質**：純 stdlib（`urllib`）、零第三方依賴、agent-friendly 的臺鐵查詢工具組。`pyproject.toml` 無 dependencies。
- **ToolResult 契約**（`trachecker/models.py`）：`{ok, source, query, data, error, hint}`，所有 handler 回傳此 shape。
- **agent_tools 6 支工具**（`trachecker/agent_tools.py` TOOLS；**插件層暴露 5 支**，`resolve_tra_station` 為內建 primitive 不註冊）：
  1. `resolve_tra_station` — 站名→TDX StationID
  2. `search_tra_od_timetable` — OD 每日時刻表
  3. `get_tra_station_live_board` — 車站即時到離站
  4. `get_tra_train_live_board` — 列車即時動態
  5. `get_tra_fare_v2_estimate` — **TDX v2** ODFare 估算票價（唯一票價工具，非 v2 已排除）
  6. `get_tra_itinerary` — 行程規劃（BFS 轉乘枚舉、4 種 objective、今天自動 `depart_after=now`、無直達自動拆段提示）
- 站名正規化「台→臺」已內建；itinerary GAP-1/GAP-2 已修；65 tests passed + ruff clean。

## LineBot Rev 整合面

- **載入機制**（rev2.5.0）：`services/plugins/__init__.py` 白名單 + REQUIRED_ENV 缺項跳過 + 重名 raise + `POLICY` risk map。
- **tool loop**（`services/ai_text.py`）：`handler(**args)`；`inspect.iscoroutinefunction` 判斷 async；授權檢查 `_is_authorized(risk, user_id, user_scope)`。
- **tra 全工具皆唯讀查詢** → policy 一律 `READ_ONLY`，人人可用，無需白名單，無需動授權邏輯。
- **TDX env**：`weather` 插件已用 `TDX_CLIENT_ID` / `TDX_CLIENT_SECRET`（`.env.example` 已有），tra 插件共用同一組 env，REQUIRED_ENV 相同即可，**不需新增 config 欄位**。

## 決策定案（草擬，待使用者確認）

| # | 問題 | 提案 |
|---|------|------|
| D1 | trachecker 取得方式 | **sys.path 注入**：`services/plugins/tra.py` 內 `sys.path.append(Path(__file__).resolve().parents[3] / "trachecker")` 後 `from trachecker.agent_tools import TOOLS, dispatch`（沿用 TASK-008 草稿） |
| D2 | 工具註冊 | **暴露 5 支**（藏掉 `resolve_tra_station` primitive：其餘 5 支 handler 皆內部自行站名解析、失敗時回傳候選站名 hint，讓 Gemini 下一輪自救，此 primitive 只會多繞一輪省 schema tokens）；全 `READ_ONLY` policy、schema 直接沿用 trachecker 的 `{name, description, parameters}`（此格式與 loader 相容，weather 插件 schema 也有相同形狀） |
| D3 | handler adapter | trachecker 的 `dispatch(name, arguments)` 不符 `handler(**args)` 契約 → 每支包 `lambda _n=_name, **_kw: dispatch(_n, _kw)`（TASK-008 已實證） |
| D4 | 版本 | **rev2.6.0**（偶數 MAJOR，直接落 main，比照 rev2.5.0 特例註記）；文件組齊步 |
| D5 | CLI 話術 | trachecker ToolResult 的 `hint` / description 已含官方校正提醒與拆段提示，插件層不重複拼字，直接透傳 |
| D6 | 測試策略 | LINEBOT 側無 pytest 慣例 → 沿用 `__main__`/assert 自我檢查（比照 `hackmd_tools.py`）；trachecker 單元測試已在前驅覆蓋，此處不重複 |

## 實作步驟總覽

| 階段 | 項目 | 檔案 | 優先級 |
|------|------|------|--------|
| 1 | tra 插件檔（sys.path + 5 tool adapter + READ_ONLY policy） | `services/plugins/tra.py` | P0 |
| 2 | registry smoke：載入 6 工具、無重名 | `services/plugins/__init__.py`（不變，驗證用） | P0 |
| 3 | `.env.example` 註記 `ENABLED_PLUGINS=weather,hackmd,tra` | `.env.example` | P0 |
| 4 | README 工具清單 + 群組語義備註（tra 全 READ_ONLY） | `README.md` | P1 |
| 5 | CHANGELOG rev2.6.0 條目 | `CHANGELOG.md` | P1 |
| 6 | MEMOIR 決策紀錄 | `MEMOIR.md` | P1 |
| 7 | 版本字串同步 2.5.0 → 2.6.0 | 全部 .py 版本頭 | P1 |

## 風險與邊界

- **不修改 trachecker 前驅專案**：本輪只動 LINEBOT_REV（`sys.path` 注入讀取前驅現況），trachecker 保持 on-hold 語義不變。
- **SPEC 不動**：依 rev2.5.0 D6 機制化決策，新增 plugin 不再觸動 SPEC（機制條文已通用）；工具資產清單一律收進 README。
- **loader 失敗模式**：`importlib.import_module` 包在 try/except（print + skip），trachecker 目錄缺失或不具 REQUIRED_ENV → 插件「靜默跳過」而非拖垮整包；部署時需以 log 確認 tra 6 工具確實載入。
- **itinerary 限制**（前驅已證實）：無直達 OD（六家→臺北）需拆段；跨午夜不延伸；`cheapest` 未實作 → 這三項為前驅設計限制，插件層不解決，靠 description/hint 傳達。
- **`parents[3]` 路徑依賴**：`tra.py` 在 `LINEBOT_REV/services/plugins/`，`parents[3]` = 兩專案共同父目錄；部署環境若無 `trachecker` 目錄則插件載入失敗（REQUIRED_ENV 檢查**不會**擋到 import 錯誤，需確定部署機有該目錄或改 pip 安裝）。