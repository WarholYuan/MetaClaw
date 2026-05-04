"""
Tests for memory summarizer: MemoryFlushManager helpers,
ensure_daily_memory_file, create_memory_files_if_needed.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.memory.summarizer import (
    MemoryFlushManager,
    ensure_daily_memory_file,
    create_memory_files_if_needed,
    SUMMARIZE_SYSTEM_PROMPT,
    SUMMARIZE_USER_PROMPT,
    DREAM_SYSTEM_PROMPT,
    DREAM_USER_PROMPT,
)


# ─────────────────── fixtures ───────────────────

@pytest.fixture
def workspace_dir():
    """Temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def flush_manager(workspace_dir):
    """MemoryFlushManager without LLM model."""
    return MemoryFlushManager(workspace_dir=workspace_dir, llm_model=None)


# ─────────────────── File path tests ───────────────────

def test_get_today_memory_file(flush_manager):
    """Today's memory file path is correct."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = flush_manager.get_today_memory_file()
    assert path.name == f"{today}.md"
    assert "memory" in str(path)


def test_get_today_memory_file_with_user(flush_manager):
    """User-scoped memory file path."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = flush_manager.get_today_memory_file(user_id="user123")
    assert "users" in str(path)
    assert "user123" in str(path)
    assert path.name == f"{today}.md"


def test_get_today_memory_file_ensure_exists(flush_manager, workspace_dir):
    """Ensure exists creates the file."""
    path = flush_manager.get_today_memory_file(ensure_exists=True)
    assert path.exists()
    content = path.read_text()
    assert "# Daily Memory:" in content


def test_get_today_memory_file_with_user_ensure_exists(flush_manager, workspace_dir):
    """Ensure exists with user creates the file in user dir."""
    path = flush_manager.get_today_memory_file(user_id="user456", ensure_exists=True)
    assert path.exists()
    assert "user456" in str(path)


def test_get_main_memory_file(flush_manager):
    """Main memory file is in workspace root."""
    path = flush_manager.get_main_memory_file()
    assert path.name == "MEMORY.md"


def test_get_main_memory_file_with_user(flush_manager):
    """User-scoped main memory file."""
    path = flush_manager.get_main_memory_file(user_id="user789")
    assert "users" in str(path)
    assert "user789" in str(path)
    assert path.name == "MEMORY.md"


def test_get_status(flush_manager):
    """Status dict has expected keys."""
    status = flush_manager.get_status()
    assert "last_flush_time" in status
    assert "today_file" in status
    assert "main_file" in status
    assert status["last_flush_time"] is None  # No flush yet


# ─────────────────── Static helpers ───────────────────

def test_extract_text_from_content_string():
    """Extract text from plain string content."""
    result = MemoryFlushManager._extract_text_from_content("hello world")
    assert result == "hello world"


def test_extract_text_from_content_blocks():
    """Extract text from Claude-format content blocks."""
    content = [
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": "World"},
        {"type": "tool_use", "id": "tool_1", "name": "bash"},
    ]
    result = MemoryFlushManager._extract_text_from_content(content)
    assert "Hello" in result
    assert "World" in result
    assert "tool_use" not in result


def test_extract_text_from_content_mixed():
    """Extract text from mixed content (strings + dicts in list)."""
    content = [
        "plain string part",
        {"type": "text", "text": "block part"},
    ]
    result = MemoryFlushManager._extract_text_from_content(content)
    assert "plain string part" in result
    assert "block part" in result


def test_extract_text_from_content_empty():
    """Empty content returns empty string."""
    assert MemoryFlushManager._extract_text_from_content("") == ""
    assert MemoryFlushManager._extract_text_from_content([]) == ""
    assert MemoryFlushManager._extract_text_from_content({}) == ""


def test_extract_first_meaningful_line():
    """Extract first meaningful line from text."""
    text = "# Heading\n\n## Subheading\n\nThis is the actual content.\nMore content."
    result = MemoryFlushManager._extract_first_meaningful_line(text)
    assert "actual content" in result


def test_extract_first_meaningful_line_markdown_noise():
    """Markdown headings, code fences, and separators are skipped."""
    text = "```\ncode block\n```\n\n---\n\nReal text here."
    result = MemoryFlushManager._extract_first_meaningful_line(text)
    assert "Real text" in result


def test_extract_first_meaningful_line_short():
    """Lines under 5 chars are skipped."""
    text = "A\nB\nC\nThis is long enough to be meaningful."
    result = MemoryFlushManager._extract_first_meaningful_line(text)
    assert "long enough" in result


def test_extract_first_meaningful_line_emoji_skip():
    """Emoji-only lines are skipped."""
    text = "😊🎉\n\nActual meaningful content."
    result = MemoryFlushManager._extract_first_meaningful_line(text)
    assert "meaningful content" in result


def test_clean_summary_output():
    """Clean summary output strips markers."""
    raw = "[DAILY]\n- Event 1\n- Event 2\n\n[MEMORY]\n- Memory item"
    result = MemoryFlushManager._clean_summary_output(raw)
    assert "[DAILY]" not in result
    assert "[MEMORY]" not in result
    assert "Event 1" in result
    assert "Event 2" in result
    assert "Memory item" not in result  # [MEMORY] section is removed


def test_clean_summary_output_daily_only():
    """Clean summary with only [DAILY] marker."""
    raw = "[DAILY]\n- Just daily events"
    result = MemoryFlushManager._clean_summary_output(raw)
    assert "Just daily events" in result
    assert "[DAILY]" not in result


def test_clean_summary_output_none():
    """Empty or '无' summaries return empty string."""
    assert MemoryFlushManager._clean_summary_output("") == ""
    assert MemoryFlushManager._clean_summary_output("无") == ""


def test_clean_summary_output_code_fences():
    """Code fences are removed."""
    raw = "[DAILY]\n```\n- Event\n```"
    result = MemoryFlushManager._clean_summary_output(raw)
    assert "```" not in result
    assert "Event" in result


def test_parse_dream_output():
    """Parse Dream output into memory and diary sections."""
    raw = "[MEMORY]\n- Memory item 1\n- Memory item 2\n\n[DREAM]\nToday I found..."
    mem, dream = MemoryFlushManager._parse_dream_output(raw)
    assert "Memory item 1" in mem
    assert "Memory item 2" in mem
    assert "Today I found" in dream


def test_parse_dream_output_memory_only():
    """Parse output with only [MEMORY] section."""
    raw = "[MEMORY]\n- Memory only"
    mem, dream = MemoryFlushManager._parse_dream_output(raw)
    assert "Memory only" in mem
    assert dream == ""


def test_parse_dream_output_dream_only():
    """Parse output with only [DREAM] section."""
    raw = "[DREAM]\nJust a dream"
    mem, dream = MemoryFlushManager._parse_dream_output(raw)
    assert mem == ""
    assert "Just a dream" in dream


def test_format_conversation_for_summary(flush_manager):
    """Format messages into readable conversation text."""
    messages = [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"},
        {"role": "user", "content": "Can you help me with Python?"},
    ]
    result = flush_manager._format_conversation_for_summary(messages)
    assert "用户: Hello" in result
    assert "助手: I'm doing well" in result


def test_format_conversation_for_summary_content_blocks(flush_manager):
    """Format messages with content blocks."""
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "Help me"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Sure!"}]},
    ]
    result = flush_manager._format_conversation_for_summary(messages)
    assert "用户: Help me" in result
    assert "助手: Sure!" in result


def test_format_conversation_max_messages(flush_manager):
    """Max messages limits the output."""
    messages = []
    for i in range(20):
        messages.append({"role": "user", "content": f"Question {i}"})
        messages.append({"role": "assistant", "content": f"Answer {i}"})

    result = flush_manager._format_conversation_for_summary(messages, max_messages=3)
    # Should only include the last 3*2 = 6 messages
    assert "Question 16" not in result  # Earlier content cut off (last 3 pairs = Q17-Q19)
    assert "Question 19" in result  # Last message present


def test_extract_summary_fallback(flush_manager):
    """Rule-based summary fallback."""
    messages = [
        {"role": "user", "content": "What's the weather?"},
        {"role": "assistant", "content": "# Weather Report\n\nIt's sunny today."},
    ]
    result = flush_manager._extract_summary_fallback(messages)
    assert "天气" in result or "weather" in result.lower() or "Weather" in result


def test_extract_summary_fallback_ignores_noise(flush_manager):
    """Fallback ignores markdown noise and short user messages."""
    messages = [
        {"role": "user", "content": "hi"},  # Too short, ignored
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "I need help with my project"},
        {"role": "assistant", "content": "# Summary\n\nLet me help you with that."},
    ]
    result = flush_manager._extract_summary_fallback(messages)
    assert "project" in result or "help" in result.lower()


# ─────────────────── Module-level file helpers ───────────────────

def test_ensure_daily_memory_file(workspace_dir):
    """ensure_daily_memory_file creates today's file if needed."""
    path = ensure_daily_memory_file(workspace_dir)
    assert path.exists()
    today = datetime.now().strftime("%Y-%m-%d")
    assert today in str(path)
    content = path.read_text()
    assert "# Daily Memory:" in content

    # Second call should return the same file
    path2 = ensure_daily_memory_file(workspace_dir)
    assert path2 == path


def test_ensure_daily_memory_file_with_user(workspace_dir):
    """User-scoped daily memory file."""
    path = ensure_daily_memory_file(workspace_dir, user_id="test_user")
    assert path.exists()
    assert "users" in str(path)
    assert "test_user" in str(path)


def test_create_memory_files_if_needed(workspace_dir):
    """Creates MEMORY.md in workspace root."""
    create_memory_files_if_needed(workspace_dir)
    main_memory = workspace_dir / "MEMORY.md"
    assert main_memory.exists()
    memory_dir = workspace_dir / "memory"
    assert memory_dir.exists()


def test_create_memory_files_if_needed_with_user(workspace_dir):
    """Creates user-scoped MEMORY.md."""
    create_memory_files_if_needed(workspace_dir, user_id="user_scoped")
    user_memory = workspace_dir / "memory" / "users" / "user_scoped" / "MEMORY.md"
    assert user_memory.exists()


# ─────────────────── Prompt template tests ───────────────────

def test_summarize_prompts_format():
    """Summarize prompts contain expected placeholders."""
    assert "{conversation}" in SUMMARIZE_USER_PROMPT
    assert "对话记录" in SUMMARIZE_SYSTEM_PROMPT


def test_dream_prompts_format():
    """Dream prompts contain expected placeholders."""
    assert "{memory_content}" in DREAM_USER_PROMPT
    assert "{daily_content}" in DREAM_USER_PROMPT
    assert "{days}" in DREAM_USER_PROMPT
    assert "[MEMORY]" in DREAM_SYSTEM_PROMPT
    assert "[DREAM]" in DREAM_SYSTEM_PROMPT


# ─────────────────── Flush pipeline tests (no LLM) ───────────────────

def test_flush_from_messages_no_llm(flush_manager):
    """Flush with no LLM uses fallback."""
    messages = [
        {"role": "user", "content": "Hello world"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    # Without LLM, flush_from_messages dispatches async thread.
    # The thread will use fallback summarization.
    result = flush_manager.flush_from_messages(messages, reason="trim")
    assert result is True  # Dispatched successfully


def test_flush_from_messages_empty_content(flush_manager):
    """Flush with empty messages returns False."""
    messages = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": ""},
    ]
    result = flush_manager.flush_from_messages(messages, reason="trim")
    assert result is False  # No deduped messages


def test_flush_from_messages_dedup(flush_manager):
    """Repeated flush with same content is deduplicated."""
    messages = [
        {"role": "user", "content": "Unique question"},
        {"role": "assistant", "content": "Unique answer"},
    ]

    result1 = flush_manager.flush_from_messages(messages, reason="trim")
    assert result1 is True

    # Second flush with same content should be deduped
    result2 = flush_manager.flush_from_messages(messages, reason="trim")
    assert result2 is False


def test_create_daily_summary_same_content(flush_manager):
    """Daily summary skips when content hasn't changed."""
    messages = [
        {"role": "user", "content": "Test"},
    ]
    result1 = flush_manager.create_daily_summary(messages)
    assert result1 is True  # First time

    result2 = flush_manager.create_daily_summary(messages)
    assert result2 is False  # Same content, skipped


def test_deep_dream_no_llm(flush_manager):
    """Deep dream without LLM returns False gracefully."""
    result = flush_manager.deep_dream()
    assert result is False
