"""驗證 AITextService / AIImageService 的 MODEL_LIST fallback / 重試 / markfail 冷卻邏輯（模擬 503/429）。

與 config.MODEL_LIST 順序無關：以 list 的第 0/1 個候選作為「主力/備援」，markfail=True 者動態取。
執行：python3 tools/test_fallback.py
"""
import importlib.util
import os
import sys
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 直接載入 ai_text 模組，避開 services/__init__ 對 apscheduler 等環境相依的匯入
_spec = importlib.util.spec_from_file_location(
    "ai_text", os.path.join(ROOT, "services", "ai_text.py")
)
ai_text = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ai_text)
AITextService = ai_text.AITextService

# 不真正等待退避
ai_text.time = SimpleNamespace(monotonic=time.monotonic, sleep=lambda *_: None)

# 從實際 MODEL_LIST 動態取「主力/備援/markfail 模型」，測試不綁死模型名稱
_MODELS = [c["model"] for c in ai_text.MODEL_LIST]
PRIMARY, BACKUP = _MODELS[0], _MODELS[1]
MARKFAIL_MODEL = next(c["model"] for c in ai_text.MODEL_LIST if c.get("markfail"))


class Fake503(Exception):
    code = 503


class Fake429(Exception):
    code = 429


class Fake400(Exception):
    code = 400


def make_service(behavior):
    """behavior: model -> Exception（拋出）或 (text,)（成功回應）"""
    svc = AITextService()
    calls = []

    def fake_generate(model, contents=None, config=None):
        calls.append(model)
        outcome = behavior[model]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome[0])

    svc._get_client = lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=fake_generate)
    )
    return svc, calls


def run_case(name, fn):
    try:
        fn()
        print(f"PASS  {name}")
        return True
    except AssertionError as e:
        print(f"FAIL  {name}: {e}")
        return False


results = []

# 1. 主力模型 503 -> fallback 到下一個候選（先重試 2 次）
def t1():
    svc, calls = make_service({
        PRIMARY: Fake503(),
        BACKUP: ("hello",),
    })
    assert svc.chat("hi") == "hello"
    assert calls[-1] == BACKUP, calls
    assert calls.count(PRIMARY) == 3, calls


results.append(run_case("fallback on 503", t1))

# 2. 503 先重試 2 次（共 3 次嘗試）才降級
def t2():
    svc, calls = make_service({
        PRIMARY: Fake503(),
        BACKUP: ("hello",),
    })
    svc.chat("hi")
    assert calls == [PRIMARY] * 3 + [BACKUP], calls


results.append(run_case("retry twice before fallback", t2))

# 3. markfail=True 失敗後標記，冷卻期內後續請求直接跳過
#    與順序無關：取列表中第一個 markfail=True 的模型及其下一個候選。
#    所有更前面的候選一律 Fake503（確保跑到 markfail 模型）。
def t3():
    idx = next(i for i, c in enumerate(ai_text.MODEL_LIST) if c.get("markfail"))
    mf_model = ai_text.MODEL_LIST[idx]["model"]
    nxt = ai_text.MODEL_LIST[idx + 1]["model"]
    behavior = {c["model"]: Fake503() for c in ai_text.MODEL_LIST}
    behavior[nxt] = ("hello",)

    svc, calls = make_service(behavior)
    svc.chat("hi")
    assert mf_model in svc._failed_marks
    calls.clear()
    svc.chat("hi")
    assert mf_model not in calls, calls


results.append(run_case("markfail cooldown skip", t3))

# 4. 全鏈失敗 -> RuntimeError；只有 markfail=True 者被標記
def t4():
    behavior = {c["model"]: Fake503() for c in ai_text.MODEL_LIST}
    svc, _ = make_service(behavior)
    try:
        svc.chat("hi")
        raise AssertionError("should raise RuntimeError")
    except RuntimeError:
        pass
    assert list(svc._failed_marks) == [MARKFAIL_MODEL], svc._failed_marks


results.append(run_case("all-fail raises RuntimeError; only markfail=True marked", t4))

# 5. 429 同樣可重試
def t5():
    svc, calls = make_service({
        PRIMARY: Fake429(),
        BACKUP: ("hello",),
    })
    assert svc.chat("hi") == "hello"
    assert calls == [PRIMARY] * 3 + [BACKUP], calls


results.append(run_case("429 is retryable", t5))

# 6. 不可重試錯誤（如 400）不重試，直接換候選
def t6():
    svc, calls = make_service({
        PRIMARY: Fake400(),
        BACKUP: ("hello",),
    })
    assert svc.chat("hi") == "hello"
    assert calls == [PRIMARY, BACKUP], calls


results.append(run_case("non-retryable skips retry", t6))


def _load_image():
    _spec = importlib.util.spec_from_file_location(
        "ai_image", os.path.join(ROOT, "services", "ai_image.py")
    )
    ai_image = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(ai_image)
    ai_image.time = SimpleNamespace(monotonic=time.monotonic, sleep=lambda *_: None)
    return ai_image


# 7. 圖片路徑 _generate 同樣走 MODEL_LIST fallback（比照文字）
def t7():
    ai_image = _load_image()
    AIImageService = ai_image.AIImageService
    idx = next(i for i, c in enumerate(ai_image.MODEL_LIST) if c.get("markfail"))
    mf_model = ai_image.MODEL_LIST[idx]["model"]
    nxt = ai_image.MODEL_LIST[idx + 1]["model"]

    svc = AIImageService()
    calls = []
    behavior = {c["model"]: Fake503() for c in ai_image.MODEL_LIST}
    behavior[nxt] = "ok"

    def fake_generate(model, contents=None):
        calls.append(model)
        if isinstance(behavior[model], str):
            return SimpleNamespace(text=behavior[model])
        raise behavior[model]

    # 只測 _generate 的 fallback 迴圈（輸入方法已由 analyze_image 封裝）
    client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate))
    resp = svc._generate(client=client, contents=["?", "img"])
    assert resp.text == "ok"
    assert calls[-4:] == [mf_model] * 3 + [nxt], calls
    assert mf_model in svc._failed_marks


results.append(run_case("image _generate fallback on 503", t7))


# 8. 圖片路徑全部失敗 -> RuntimeError
def t8():
    ai_image = _load_image()
    AIImageService = ai_image.AIImageService
    svc = AIImageService()
    behavior = {c["model"]: Fake503() for c in ai_image.MODEL_LIST}
    client = SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda model, contents=None: (_ for _ in ()).throw(behavior[model])
    ))
    try:
        svc._generate(client=client, contents=["?", "img"])
        raise AssertionError("should raise RuntimeError")
    except RuntimeError:
        pass
    markfail = next(c["model"] for c in ai_image.MODEL_LIST if c.get("markfail"))
    assert list(svc._failed_marks) == [markfail], svc._failed_marks


results.append(run_case("image all-fail raises RuntimeError", t8))


print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
