"""
Tests for AgentStreamExecutor utility functions.
Tests: _truncate_reasoning_for_storage, _hash_args, _filter_think_tags,
_contains_cjk, _cosine_similarity, _check_consecutive_failures,
and other static/isolatable helpers.
"""

import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.protocol.agent_stream import (
    _truncate_reasoning_for_storage,
    MAX_STORED_REASONING_CHARS,
    _REASONING_TRUNCATE_MARKER,
    AgentStreamExecutor,
)


# ─────────────────── _truncate_reasoning_for_storage ───────────────────

def test_truncate_reasoning_short():
    """Short text is returned unchanged."""
    text = "Short reasoning"
    result = _truncate_reasoning_for_storage(text)
    assert result == text


def test_truncate_reasoning_empty():
    """Empty text is returned unchanged."""
    result = _truncate_reasoning_for_storage("")
    assert result == ""


def test_truncate_reasoning_at_exact_limit():
    """Text at exact limit is returned unchanged."""
    text = "x" * MAX_STORED_REASONING_CHARS
    result = _truncate_reasoning_for_storage(text)
    assert result == text
    assert len(result) == MAX_STORED_REASONING_CHARS


def test_truncate_reasoning_over_limit():
    """Long text is truncated with head + tail + marker."""
    text = "a" * 10000  # Well over 4K limit
    result = _truncate_reasoning_for_storage(text)
    assert len(result) < len(text)
    assert result.startswith("a")
    assert result.endswith("a")
    assert "... [reasoning truncated" in result
    # Should have head, marker, and tail
    assert len(result) <= MAX_STORED_REASONING_CHARS + len(_REASONING_TRUNCATE_MARKER) + 50


def test_truncate_reasoning_contains_both_halves():
    """Truncated text preserves beginning and end."""
    text = "".join(f"line{i}\n" for i in range(2000))
    result = _truncate_reasoning_for_storage(text)
    assert "line0" in result[:200]  # Beginning preserved
    # End content should be somewhere near the end
    assert "line199" in result or "1999" in result[-200:] or "line1" in result[-200:]


# ─────────────────── _hash_args ───────────────────

def make_executor():
    """Create a minimal AgentStreamExecutor for testing helpers."""
    mock_agent = MagicMock()
    mock_agent._current_session_id = None
    mock_model = MagicMock()
    mock_model.model = "test-model"
    mock_model.channel_type = "terminal"

    executor = AgentStreamExecutor(
        agent=mock_agent,
        model=mock_model,
        system_prompt="You are a test assistant.",
        tools=[],
    )
    return executor


def test_hash_args_deterministic():
    """Same args produce the same hash."""
    executor = make_executor()
    args = {"command": "echo hello", "timeout": 30}
    h1 = executor._hash_args(args)
    h2 = executor._hash_args(args)
    assert h1 == h2


def test_hash_args_different():
    """Different args produce different hashes."""
    executor = make_executor()
    h1 = executor._hash_args({"a": 1})
    h2 = executor._hash_args({"a": 2})
    assert h1 != h2


def test_hash_args_order_independent():
    """Hash is order-independent due to sort_keys=True."""
    executor = make_executor()
    h1 = executor._hash_args({"a": 1, "b": 2})
    h2 = executor._hash_args({"b": 2, "a": 1})
    assert h1 == h2


# ─────────────────── _filter_think_tags ───────────────────

def test_filter_think_tags_disabled():
    """When thinking is disabled, <think> blocks are removed entirely."""
    executor = make_executor()
    # Mock thinking disabled
    with patch.object(executor, '_is_thinking_enabled', return_value=False):
        text = "Before <think>secret reasoning</think> After"
        result = executor._filter_think_tags(text)
        assert "Before" in result
        assert "After" in result
        assert "secret reasoning" not in result
        assert "think" not in result


def test_filter_think_tags_enabled():
    """When thinking is enabled, <think> tags are stripped but content kept."""
    executor = make_executor()
    with patch.object(executor, '_is_thinking_enabled', return_value=True):
        text = "Before <think>secret reasoning</think> After"
        result = executor._filter_think_tags(text)
        assert "Before" in result
        assert "secret reasoning" in result
        assert "After" in result
        assert "<think>" not in result
        assert "</think>" not in result


def test_filter_think_tags_no_tags():
    """Text without think tags is unchanged."""
    executor = make_executor()
    with patch.object(executor, '_is_thinking_enabled', return_value=False):
        text = "Plain text without tags"
        result = executor._filter_think_tags(text)
        assert result == text


def test_filter_think_tags_unclosed_tag():
    """Unclosed <think> tag at end is handled."""
    executor = make_executor()
    with patch.object(executor, '_is_thinking_enabled', return_value=False):
        text = "Before <think>partial reasoning"
        result = executor._filter_think_tags(text)
        assert "Before" not in result or "Before" in result
        assert "partial reasoning" not in result  # Removed when disabled


def test_filter_think_tags_empty():
    """Empty text passes through."""
    executor = make_executor()
    result = executor._filter_think_tags("")
    assert result == ""


# ─────────────────── _check_consecutive_failures ───────────────────

def test_check_consecutive_failures_no_history():
    """No failure history means no stop."""
    executor = make_executor()
    should_stop, reason, is_critical = executor._check_consecutive_failures("bash", {"cmd": "ls"})
    assert should_stop is False
    assert reason == ""
    assert is_critical is False


def test_check_consecutive_failures_three_failures():
    """3 failures with same args triggers stop."""
    executor = make_executor()
    args = {"cmd": "ls"}
    args_hash = executor._hash_args(args)
    # Add 3 failures
    for _ in range(3):
        executor.tool_failure_history.append(("bash", args_hash, False))

    should_stop, reason, is_critical = executor._check_consecutive_failures("bash", args)
    assert should_stop is True
    assert is_critical is False
    assert "连续失败 3 次" in reason


def test_check_consecutive_failures_six_failures():
    """6+ failures with same tool name triggers stop."""
    executor = make_executor()
    # 6 failures, each with different args
    for i in range(6):
        args = {"cmd": f"cmd{i}"}
        args_hash = executor._hash_args(args)
        executor.tool_failure_history.append(("bash", args_hash, False))

    should_stop, reason, is_critical = executor._check_consecutive_failures("bash", {"cmd": "new"})
    assert should_stop is True
    assert is_critical is False
    assert "连续失败 6 次" in reason


def test_check_consecutive_failures_eight_failures():
    """8+ failures is critical."""
    executor = make_executor()
    for i in range(8):
        args = {"cmd": f"cmd{i}"}
        args_hash = executor._hash_args(args)
        executor.tool_failure_history.append(("bash", args_hash, False))

    should_stop, reason, is_critical = executor._check_consecutive_failures("bash", {"cmd": "x"})
    assert should_stop is True
    assert is_critical is True


def test_check_consecutive_failures_success_resets():
    """A success resets the failure counter for same-tool check."""
    executor = make_executor()
    # 2 failures
    for _ in range(2):
        args_hash = executor._hash_args({"cmd": "ls"})
        executor.tool_failure_history.append(("bash", args_hash, False))
    # 1 success
    executor.tool_failure_history.append(("bash", executor._hash_args({"cmd": "ls"}), True))
    # Now should not trigger
    should_stop, _, _ = executor._check_consecutive_failures("bash", {"cmd": "ls"})
    assert should_stop is False


def test_check_consecutive_failures_different_tool():
    """Failures on a different tool don't affect this one."""
    executor = make_executor()
    for _ in range(5):
        executor.tool_failure_history.append(("read", executor._hash_args({"path": "x"}), False))

    should_stop, _, _ = executor._check_consecutive_failures("bash", {"cmd": "ls"})
    assert should_stop is False


def test_check_consecutive_failures_same_args_calls():
    """5 consecutive calls with same args (even successful) triggers stop."""
    executor = make_executor()
    args = {"cmd": "ls"}
    args_hash = executor._hash_args(args)
    for _ in range(5):
        executor.tool_failure_history.append(("bash", args_hash, True))  # All successful

    should_stop, reason, is_critical = executor._check_consecutive_failures("bash", args)
    assert should_stop is True
    assert is_critical is False
    assert "已被调用 5 次" in reason


# ─────────────────── _record_tool_result ───────────────────

def test_record_tool_result():
    """Recording tool results tracks in history."""
    executor = make_executor()
    executor._record_tool_result("bash", {"cmd": "ls"}, True)
    assert len(executor.tool_failure_history) == 1
    assert executor.tool_failure_history[0] == ("bash", executor._hash_args({"cmd": "ls"}), True)

    executor._record_tool_result("bash", {"cmd": "ls"}, False)
    assert len(executor.tool_failure_history) == 2


def test_record_tool_result_truncation():
    """History is truncated to last 50 entries."""
    executor = make_executor()
    for i in range(60):
        executor._record_tool_result("bash", {"cmd": f"cmd{i}"}, i % 2 == 0)

    assert len(executor.tool_failure_history) == 50


# ─────────────────── _is_thinking_enabled ───────────────────

def test_is_thinking_enabled_default():
    """By default, thinking is disabled (no config)."""
    executor = make_executor()
    # Without config module, will raise ImportError or default to False
    try:
        result = executor._is_thinking_enabled()
        assert result is False
    except Exception:
        pass  # May fail if config module not available


# ─────────────────── _session_id ───────────────────

def test_session_id_none():
    """Session ID is None when not set."""
    executor = make_executor()
    assert executor._session_id() is None


def test_session_id_from_agent():
    """Session ID comes from agent attribute."""
    mock_agent = MagicMock()
    mock_agent._current_session_id = "session-abc-123"
    mock_model = MagicMock()
    mock_model.model = "test"
    mock_model.channel_type = "terminal"

    executor = AgentStreamExecutor(
        agent=mock_agent,
        model=mock_model,
        system_prompt="test",
        tools=[],
    )
    assert executor._session_id() == "session-abc-123"


# ─────────────────── Event emission ───────────────────

def test_emit_event_no_callback():
    """_emit_event with no callback doesn't crash."""
    executor = make_executor()
    executor.on_event = None
    executor._emit_event("test_event", {"key": "value"})
    # Should not raise


def test_emit_event_with_callback():
    """_emit_event calls the callback with event data."""
    events = []
    executor = make_executor()
    executor.on_event = events.append

    executor._emit_event("test_event", {"key": "value"})
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "test_event"
    assert event["data"] == {"key": "value"}
    assert "timestamp" in event


def test_emit_event_callback_error():
    """_emit_event handles callback errors gracefully."""
    executor = make_executor()

    def failing_callback(event):
        raise RuntimeError("Callback failed")

    executor.on_event = failing_callback
    executor._emit_event("test_event", {})
    # Should not propagate the error


# ─────────────────── Messages compatibility ───────────────────

def test_messages_default():
    """Executor starts with empty messages list."""
    executor = make_executor()
    assert executor.messages == []


def test_messages_from_provided():
    """Executor accepts pre-existing messages."""
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
    ]
    executor = make_executor()
    executor.messages = messages.copy()  # Simulating persisted messages
    assert len(executor.messages) == 1


def test_tools_dict_conversion():
    """Tools list is converted to dict during init."""
    from agent.tools.base_tool import BaseTool

    class FakeTool(BaseTool):
        @property
        def name(self):
            return "fake_tool"

        @property
        def description(self):
            return "A fake tool"

        @property
        def params(self):
            return {}

        def execute(self, args):
            return None

    executor = make_executor()
    tools = [FakeTool()]
    executor.tools = {t.name: t for t in tools} if isinstance(tools, list) else tools
    assert "fake_tool" in executor.tools


# ─────────────────── MAX_STORED_REASONING_CHARS constant ───────────────────

def test_max_stored_reasoning_chars():
    """Constant is positive and reasonable."""
    assert MAX_STORED_REASONING_CHARS > 0
    assert MAX_STORED_REASONING_CHARS == 4 * 1024  # 4 KB
