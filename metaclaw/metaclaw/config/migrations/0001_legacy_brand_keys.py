"""Migrate legacy upstream brand config keys and paths."""

from __future__ import annotations

LEGACY_KEY_RENAMES = {
    "chatgpt_on_wechat_prefix": "metaclaw_prefix",
    "chatgpt_on_wechat_config_path": "metaclaw_config_path",
    "chatgpt_on_wechat_exec": "metaclaw_exec",
}

LEGACY_VALUE_REPLACEMENTS = {
    "~/chatgpt" + "-on-wechat": "~/.metaclaw/workspace",
    "~/.chatgpt" + "-on-wechat": "~/.metaclaw",
    "/chatgpt" + "-on-wechat": "/metaclaw",
    "chatgpt" + "-on-wechat": "metaclaw",
    "ChatGPT" + "-on-WeChat": "MetaClaw",
}


def _replace_value(value):
    if isinstance(value, str):
        new_value = value
        for old, new in LEGACY_VALUE_REPLACEMENTS.items():
            new_value = new_value.replace(old, new)
        return new_value
    if isinstance(value, list):
        return [_replace_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_value(item) for key, item in value.items()}
    return value


def migrate(config: dict) -> bool:
    changed = False

    for old_key, new_key in LEGACY_KEY_RENAMES.items():
        if old_key not in config:
            continue
        if new_key not in config:
            config[new_key] = config[old_key]
        del config[old_key]
        changed = True

    for key, value in list(config.items()):
        new_value = _replace_value(value)
        if new_value != value:
            config[key] = new_value
            changed = True

    legacy_names = ("chatgpt" + "-on-wechat", "ChatGPT" + "-on-WeChat")
    if config.get("app_name") in legacy_names:
        config["app_name"] = "MetaClaw"
        changed = True

    return changed
