import os

from agent.prompt.workspace import ensure_workspace, load_context_files


def test_load_context_files_keeps_rule_authoritative(tmp_path):
    (tmp_path / "AGENT.md").write_text("agent identity", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("codex instructions", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude instructions", encoding="utf-8")
    (tmp_path / "GEMINI.md").write_text("gemini instructions", encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text(
        "copilot instructions",
        encoding="utf-8",
    )
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "project.md").write_text(
        "cursor rule",
        encoding="utf-8",
    )
    (tmp_path / ".cursorrules").write_text(
        "legacy cursor rule",
        encoding="utf-8",
    )
    (tmp_path / ".github" / "instructions").mkdir()
    (tmp_path / ".github" / "instructions" / "review.instructions.md").write_text(
        "copilot scoped instructions",
        encoding="utf-8",
    )
    (tmp_path / ".github" / "instructions" / "notes.md").write_text(
        "not a copilot instruction file",
        encoding="utf-8",
    )
    (tmp_path / "RULE.md").write_text("metaclaw rule", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("memory", encoding="utf-8")

    files = load_context_files(str(tmp_path))
    paths = [item.path for item in files]

    assert paths.index("AGENTS.md") < paths.index("RULE.md")
    assert paths.index("CLAUDE.md") < paths.index("RULE.md")
    assert paths.index("GEMINI.md") < paths.index("RULE.md")
    assert paths.index(os.path.join(".github", "copilot-instructions.md")) < paths.index("RULE.md")
    assert paths.index(os.path.join(".cursor", "rules", "project.md")) < paths.index("RULE.md")
    assert paths.index(".cursorrules") < paths.index("RULE.md")
    assert paths.index(os.path.join(".github", "instructions", "review.instructions.md")) < paths.index("RULE.md")
    assert os.path.join(".github", "instructions", "notes.md") not in paths


def test_agents_override_replaces_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("base instructions", encoding="utf-8")
    (tmp_path / "AGENTS.override.md").write_text("override instructions", encoding="utf-8")
    (tmp_path / "RULE.md").write_text("metaclaw rule", encoding="utf-8")

    files = load_context_files(str(tmp_path))
    paths = [item.path for item in files]

    assert "AGENTS.md" not in paths
    assert "AGENTS.override.md" in paths


def test_ensure_workspace_creates_tmp_dir(tmp_path):
    ensure_workspace(str(tmp_path), create_templates=False)

    assert (tmp_path / "tmp").is_dir()
