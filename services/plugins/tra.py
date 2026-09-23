"""
TRA Rail Plugin
版本: rev2.6.0
臺鐵（TRA Checker）查詢功能模組，提供 Gemini Function Calling 使用。
trachecker 前驅專案位於共同父目錄，以 sys.path 注入；目錄不可用時 loader 會跳過此插件。
"""

import sys
from pathlib import Path

_trachecker_path = Path(__file__).resolve().parents[3] / "trachecker"
if str(_trachecker_path) not in sys.path:
    sys.path.append(str(_trachecker_path))

from trachecker.agent_tools import TOOLS as _TRACHECKER_TOOLS
from trachecker.agent_tools import dispatch as _tra_dispatch

REQUIRED_ENV = ["TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]

_SKIPPED = {"resolve_tra_station"}

TOOLS = []
for _tool in _TRACHECKER_TOOLS:
    _name = _tool["name"]
    if _name in _SKIPPED:
        continue
    TOOLS.append(
        {
            "schema": _tool,
            "handler": lambda _n=_name, **_kw: _tra_dispatch(_n, _kw),
            "policy": {"risk": "READ_ONLY"},
        }
    )

if __name__ == "__main__":
    names = [t["schema"]["name"] for t in TOOLS]
    assert len(TOOLS) == 5, TOOLS
    assert names == [
        "search_tra_od_timetable",
        "get_tra_station_live_board",
        "get_tra_train_live_board",
        "get_tra_fare_v2_estimate",
        "get_tra_itinerary",
    ], names
    assert all(t["policy"]["risk"] == "READ_ONLY" for t in TOOLS)
    for t in TOOLS:
        assert callable(t["handler"])
    print(f"tra plugin self-check OK: {len(TOOLS)} tools ({', '.join(names)})")