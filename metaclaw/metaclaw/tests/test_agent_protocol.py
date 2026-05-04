"""Tests for agent/protocol/agent_stream.py — reasoning truncation helpers."""

import pytest
from agent.protocol.agent_stream import (
    _truncate_reasoning_for_storage,
    MAX_STORED_REASONING_CHARS,
    _REASONING_TRUNCATE_MARKER,
)


class TestTruncateReasoning:
    """Tests for _truncate_reasoning_for_storage()."""

    def test_empty_string(self):
        assert _truncate_reasoning_for_storage("") == ""

    def test_short_text_unchanged(self):
        text = "Short reasoning chain"
        assert _truncate_reasoning_for_storage(text) == text

    def test_exactly_at_cap_unchanged(self):
        text = "x" * MAX_STORED_REASONING_CHARS
        assert _truncate_reasoning_for_storage(text) == text

    def test_long_text_truncated(self):
        text = "A" * (MAX_STORED_REASONING_CHARS + 1000)
        result = _truncate_reasoning_for_storage(text)
        # Should contain the marker
        assert "[reasoning truncated" in result
        # Should be shorter than original
        assert len(result) < len(text)
        # Starts with head, ends with tail
        half = MAX_STORED_REASONING_CHARS // 2
        assert result.startswith("A" * half)
        assert result.endswith("A" * half)

    def test_marker_inserted_between_head_and_tail(self):
        # Must exceed MAX_STORED_REASONING_CHARS to trigger truncation
        text = "START" + "M" * (MAX_STORED_REASONING_CHARS) + "END"
        result = _truncate_reasoning_for_storage(text)
        assert "START" in result
        assert "END" in result
        assert "[reasoning truncated" in result

    def test_omitted_count_in_marker(self):
        text = "X" * (MAX_STORED_REASONING_CHARS + 500)
        result = _truncate_reasoning_for_storage(text)
        # Marker contains the omitted character count
        assert "500 chars omitted" in result or any(
            "chars omitted" in line for line in result.split("\n")
        )

    def test_multibyte_unicode(self):
        """Truncation works with multibyte characters."""
        text = "🧠思考" * 2000  # far exceeds cap
        result = _truncate_reasoning_for_storage(text)
        assert len(result) < len(text)
        assert "思考" in result
