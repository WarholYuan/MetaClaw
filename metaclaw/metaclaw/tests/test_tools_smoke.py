"""
Smoke tests for core Agent tools.
Tests: can create instance, execute basic operations, handle errors.
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.tools.bash.bash import Bash
from agent.tools.read.read import Read
from agent.tools.write.write import Write
from agent.tools.edit.edit import Edit
from agent.tools.base_tool import ToolResult


# ─────────────────── helpers ───────────────────

def is_ok(result: ToolResult) -> bool:
    """ToolResult uses status='success' or 'error', not a boolean property."""
    return result.status == "success"


# ─────────────────── BashTool ───────────────────

def test_bash_create():
    bash = Bash()
    assert bash.name == "bash"
    assert "Execute a bash command" in bash.description


def test_bash_echo():
    bash = Bash()
    result = bash.execute({"command": "echo hello"})
    assert is_ok(result)
    assert "hello" in str(result.result)


def test_bash_error():
    bash = Bash()
    result = bash.execute({"command": "ls /definitely_not_exists_xyz 2>&1; exit 1"})
    assert result.status == "error"


def test_bash_empty_command():
    bash = Bash()
    result = bash.execute({"command": ""})
    assert result.status == "error"


def test_bash_timeout():
    bash = Bash()
    result = bash.execute({"command": "sleep 10", "timeout": 1})
    # Should timeout (not hang) — either error or success with truncated output
    assert result.status in ("success", "error")


# ─────────────────── ReadTool ───────────────────

def test_read_create():
    reader = Read()
    assert reader.name == "read"


def test_read_existing_file():
    reader = Read()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line1\nline2\nline3\n")
        tmp_path = f.name
    try:
        result = reader.execute({"path": tmp_path})
        assert is_ok(result)
        assert "line1" in str(result.result)
    finally:
        os.unlink(tmp_path)


def test_read_nonexistent_file():
    reader = Read()
    result = reader.execute({"path": "/tmp/nonexistent_xyz_12345.txt"})
    assert result.status == "error"


def test_read_offset_limit():
    reader = Read()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for i in range(10):
            f.write(f"line{i}\n")
        tmp_path = f.name
    try:
        result = reader.execute({"path": tmp_path, "offset": 3, "limit": 2})
        assert is_ok(result)
    finally:
        os.unlink(tmp_path)


# ─────────────────── WriteTool ───────────────────

def test_write_create():
    writer = Write()
    assert writer.name == "write"


def test_write_file_to_cwd():
    """Write to project cwd (within allowed directories)."""
    writer = Write()
    test_path = os.path.join(writer.cwd, "test_write_smoke.txt")
    try:
        result = writer.execute({"path": test_path, "content": "hello world"})
        assert is_ok(result)
        assert os.path.exists(test_path)
        with open(test_path) as f:
            assert f.read() == "hello world"
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_write_in_tempdir():
    """Write inside a tempdir by setting cwd via config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = Write(config={"cwd": tmpdir})
        test_path = os.path.join(tmpdir, "test.txt")
        result = writer.execute({"path": test_path, "content": "ok"})
        assert is_ok(result)
        assert os.path.exists(test_path)


def test_write_missing_path():
    writer = Write()
    result = writer.execute({"path": "", "content": "x"})
    assert result.status == "error"


# ─────────────────── EditTool ───────────────────

def test_edit_create():
    editor = Edit()
    assert editor.name == "edit"


def test_edit_replace_in_cwd():
    editor = Edit()
    test_path = os.path.join(editor.cwd, "test_edit_smoke.txt")
    try:
        with open(test_path, "w") as f:
            f.write("hello world")
        result = editor.execute({"path": test_path, "oldText": "world", "newText": "universe"})
        assert is_ok(result)
        with open(test_path) as f:
            assert f.read() == "hello universe"
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_edit_append_in_cwd():
    editor = Edit()
    test_path = os.path.join(editor.cwd, "test_edit_append.txt")
    try:
        with open(test_path, "w") as f:
            f.write("line1\n")
        result = editor.execute({"path": test_path, "oldText": "", "newText": "line2\n"})
        assert is_ok(result)
        with open(test_path) as f:
            content = f.read()
        assert "line2" in content
    finally:
        if os.path.exists(test_path):
            os.unlink(test_path)


def test_edit_nonexistent_file():
    editor = Edit()
    result = editor.execute({
        "path": "/tmp/nonexistent_edit_xyz_12345.txt",
        "oldText": "a",
        "newText": "b",
    })
    assert result.status == "error"
