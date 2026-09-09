"""
Plugin System Infrastructure
版本: rev2.4.0
掃描 services/plugins/ 目錄下的插件模組，依 ENABLED_PLUGINS 白名單載入
"""

import glob
import importlib
import os

from config import config

TOOLS: list[dict] = []
DISPATCH: dict[str, callable] = {}


def _load_plugins():
    """掃描並載入啟用的插件"""
    enabled = config.enabled_plugins_list
    if not enabled:
        return

    plugin_dir = os.path.dirname(__file__)
    pattern = os.path.join(plugin_dir, "*.py")
    plugin_files = glob.glob(pattern)

    seen_names = set()

    for filepath in plugin_files:
        basename = os.path.basename(filepath)
        if basename == "__init__.py":
            continue

        module_name = basename[:-3]
        if module_name not in enabled:
            continue

        try:
            module = importlib.import_module(f"services.plugins.{module_name}")
        except Exception as e:
            print(f"[plugins] Failed to load {module_name}: {e}")
            continue

        required_env = getattr(module, "REQUIRED_ENV", [])
        for env_name in required_env:
            if not os.getenv(env_name):
                print(f"[plugins] Skip {module_name}: missing env {env_name}")
                break
        else:
            plugin_tools = getattr(module, "TOOLS", [])
            for tool in plugin_tools:
                schema = tool.get("schema", {})
                tool_name = schema.get("name", "")
                handler = tool.get("handler")

                if not callable(handler):
                    print(f"[plugins] Skip tool {tool_name}: handler not callable")
                    continue

                if tool_name in seen_names:
                    raise RuntimeError(f"Duplicate tool name: {tool_name}")

                seen_names.add(tool_name)
                TOOLS.append(schema)
                DISPATCH[tool_name] = handler


_load_plugins()
