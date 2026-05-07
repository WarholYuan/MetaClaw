"""Manifest schema for MetaClaw tool packages."""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class ToolPermissions:
    """Permission flags a tool can request from the runtime."""

    filesystem: bool = False
    shell: bool = False
    browser: bool = False
    web_search: bool = False
    opencli: bool = False


@dataclass
class ToolManifest:
    """Metadata required to publish or install a packaged tool."""

    name: str
    version: str
    description: str
    permissions: ToolPermissions
    entrypoint: str


def validate_manifest(data: Mapping[str, Any]) -> ToolManifest:
    """Validate manifest data and return a typed ``ToolManifest``.

    Raises:
        ValueError: If the manifest is missing required fields or uses invalid
            field types.
    """
    if not isinstance(data, Mapping):
        raise ValueError("Tool manifest must be an object.")

    required = ("name", "version", "description", "entrypoint")
    for field_name in required:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Tool manifest field '{field_name}' must be a non-empty string.")

    raw_permissions = data.get("permissions")
    if not isinstance(raw_permissions, Mapping):
        raise ValueError("Tool manifest field 'permissions' must be an object.")

    allowed = ("filesystem", "shell", "browser", "web_search", "opencli")
    unexpected = sorted(set(raw_permissions) - set(allowed))
    if unexpected:
        raise ValueError("Unknown tool permission flag(s): " + ", ".join(unexpected))

    permissions = {}
    for key in allowed:
        value = raw_permissions.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"Tool permission '{key}' must be a boolean.")
        permissions[key] = value

    return ToolManifest(
        name=data["name"].strip(),
        version=data["version"].strip(),
        description=data["description"].strip(),
        permissions=ToolPermissions(**permissions),
        entrypoint=data["entrypoint"].strip(),
    )
