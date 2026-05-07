import importlib
import json
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.tools import OpenCLITool
from agent.tools.opencli.opencli_tool import _try_parse_json


class Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_opencli_tool_reports_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)

    tool = OpenCLITool()
    result = tool.execute({"mode": "browser", "command": "state"})

    assert result.status == "error"
    assert "opencli is not installed" in result.result


def test_opencli_tool_is_exported_for_tool_registration():
    tools_module = importlib.import_module("agent.tools")

    assert "OpenCLITool" in tools_module.__all__
    assert tools_module.OpenCLITool is OpenCLITool


def test_opencli_tool_validates_required_args(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/opencli")

    tool = OpenCLITool()

    assert tool.execute({"mode": "", "command": "state"}).status == "error"
    assert tool.execute({"mode": "browser", "command": ""}).status == "error"
    assert tool.execute({"mode": "unknown", "command": "state"}).status == "error"


def test_opencli_tool_runs_browser_command_and_formats_json(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/opencli")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Completed(stdout=json.dumps({"ok": True, "items": [1]}))

    monkeypatch.setattr("subprocess.run", fake_run)

    result = OpenCLITool().execute({"mode": "browser", "command": "state"})

    assert result.status == "success"
    assert calls == [["opencli", "browser", "state"]]
    assert '"ok": true' in result.result


def test_opencli_tool_returns_structured_error_on_nonzero(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/opencli")
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: Completed(returncode=2, stdout='{"error":"bad"}'),
    )

    result = OpenCLITool().execute({"mode": "adapter", "command": "github issues"})

    assert result.status == "error"
    assert "bad" in result.result


def test_opencli_tool_handles_timeout(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/opencli")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr("subprocess.run", fake_run)

    result = OpenCLITool().execute({"mode": "browser", "command": "state", "timeout": 1})

    assert result.status == "error"
    assert "timed out" in result.result


def test_try_parse_json_rejects_plain_text():
    assert _try_parse_json("plain text") is None
    assert _try_parse_json('{"ok": true}') == {"ok": True}
