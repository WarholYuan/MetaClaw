"""Manifest schema for distributable MetaClaw skills."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class SkillManifest:
    """Metadata required to publish or install a packaged skill."""

    name: str
    version: str
    description: str
    entrypoint: str
    permissions: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    author: Optional[str] = None
    homepage: Optional[str] = None


def validate_manifest(data: Mapping[str, Any]) -> SkillManifest:
    """Validate manifest data and return a typed ``SkillManifest``.

    Raises:
        ValueError: If the manifest is missing required fields or uses invalid
            field types.
    """
    if not isinstance(data, Mapping):
        raise ValueError("Skill manifest must be an object.")

    required = ("name", "version", "description", "entrypoint")
    for field_name in required:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Skill manifest field '{field_name}' must be a non-empty string.")

    permissions = data.get("permissions", [])
    if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
        raise ValueError("Skill manifest field 'permissions' must be a list of strings.")

    config_schema = data.get("config_schema", {})
    if not isinstance(config_schema, dict):
        raise ValueError("Skill manifest field 'config_schema' must be an object.")

    author = data.get("author")
    if author is not None and not isinstance(author, str):
        raise ValueError("Skill manifest field 'author' must be a string when provided.")

    homepage = data.get("homepage")
    if homepage is not None and not isinstance(homepage, str):
        raise ValueError("Skill manifest field 'homepage' must be a string when provided.")

    return SkillManifest(
        name=data["name"].strip(),
        version=data["version"].strip(),
        description=data["description"].strip(),
        entrypoint=data["entrypoint"].strip(),
        permissions=list(permissions),
        config_schema=dict(config_schema),
        author=author.strip() if isinstance(author, str) else None,
        homepage=homepage.strip() if isinstance(homepage, str) else None,
    )
