# Project AGENTS

任務開始前，優先查閱 `agentmemory` 與 `redis-submemory` 的最新 checkpoint 與相關記憶。
若有可用記憶，先以既有決策、風險與進度為準，再進行本地代碼與文件掃描。
若記憶不可用或查無資料，則以當前 repository 狀態為準。
任務結束前，將重要決策、版本、風險與進度回寫至 `agentmemory` 與 `redis-submemory`，形成閉環。

## Repo Rules

- 所有 shell 指令優先使用 `rtk` 前綴。
- 讀檔與掃描優先使用 `rg`、`sed`、`git diff`、`git show`，避免不必要的廣泛探測。
- 手動改檔一律使用 `apply_patch`，不要用 `cat > file` 這類方式直接寫檔。
- 不要回退、覆蓋或刪除你沒有明確負責的變更。
- 不要在未經確認下使用破壞性 git 指令，例如 `git reset --hard` 或 `git checkout --`。
- 若要提交，使用非互動式 git 指令，且預設只做本地 commit，不自動 push。

## Development Rules

- main 分支版本號使用偶數 MAJOR；feature 或測試分支使用奇數 MAJOR。
- 已合併到 main 的功能若涉及版本文件，必須同步更新 `CHANGELOG.md`、`README.md`、`SPEC.md`、`MEMOIR.md`。
- keepalive 不可在 worker import 階段自動啟動；只允許在明確的請求生命週期或直接執行入口啟動。
- `/api/db/restore` 與 `/api/db/validate` 這類上傳還原路徑預設視為高風險，不得在未確認前重新啟用。
- 如需加入新的環境變數，必須同步更新 `config.py`、`.env.example`，並確認 `Config.__post_init__` 有載入。
- 若新增/修改與資料庫相關功能，先確認不會影響 Render 啟動穩定性與現有 webhook 回覆。

## Memory Workflow

- 大型任務或跨階段任務開始前，先讀 `agentmemory` 與 `redis-submemory` 的 checkpoint。
- 任務中若出現明確決策、風險或版本變更，立即回寫記憶。
- 任務完成後，補寫最終狀態與可延續的下一步，避免下次 session 重複分析。
