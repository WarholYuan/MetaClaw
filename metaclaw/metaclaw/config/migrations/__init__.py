"""Config migration framework for MetaClaw."""

from __future__ import annotations

import importlib
import json
import os
import pkgutil
from typing import Callable, Iterable

from common.brand import DEFAULT_AGENT_WORKSPACE

MIGRATION_STATE_KEY = "_metaclaw_migrations"


class MigrationError(RuntimeError):
    """Raised when a config migration cannot be completed."""


def default_config_path() -> str:
    env_path = os.environ.get("METACLAW_CONFIG_FILE", "").strip()
    if env_path:
        return os.path.expanduser(env_path)
    return os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "config.json"))


def default_config_paths() -> list[str]:
    env_path = os.environ.get("METACLAW_CONFIG_FILE", "").strip()
    if env_path:
        return [os.path.expanduser(env_path)]

    candidates = [
        "~/.metaclaw/config.json",
        os.path.join(DEFAULT_AGENT_WORKSPACE, "config.json"),
        "./config.json",
    ]
    paths = []
    for candidate in candidates:
        path = os.path.abspath(os.path.expanduser(candidate))
        if path not in paths:
            paths.append(path)
    return paths


def _migration_modules() -> Iterable[tuple[str, Callable[[dict], bool]]]:
    package_name = __name__
    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda item: item.name):
        if not module_info.name[:4].isdigit():
            continue
        module = importlib.import_module(f"{package_name}.{module_info.name}")
        migrate = getattr(module, "migrate", None)
        if not callable(migrate):
            raise MigrationError(f"Migration {module_info.name} has no migrate(config) function")
        yield module_info.name, migrate


def _run_pending_migrations_for_path(path: str) -> list[str]:
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except Exception as exc:
        raise MigrationError(f"Could not read config file {path}: {exc}") from exc

    state = config.setdefault(MIGRATION_STATE_KEY, [])
    if not isinstance(state, list):
        state = []
        config[MIGRATION_STATE_KEY] = state

    applied = []
    changed = False
    for name, migrate in _migration_modules():
        if name in state:
            continue
        migration_changed = bool(migrate(config))
        state.append(name)
        applied.append(name)
        changed = changed or migration_changed or True

    if changed:
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)

    return applied


def run_pending_migrations(config_path: str | None = None) -> list[str]:
    """Run pending migrations against config.json and return applied names."""
    if config_path:
        return _run_pending_migrations_for_path(os.path.expanduser(config_path))

    applied = []
    for path in default_config_paths():
        for name in _run_pending_migrations_for_path(path):
            if name not in applied:
                applied.append(name)
    return applied
