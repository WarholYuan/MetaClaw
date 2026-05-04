"""Tests for channel/feishu/feishu_message.py — FeishuMessage parsing."""

import pytest
from unittest.mock import patch
from channel.feishu.feishu_message import FeishuMessage
from bridge.context import ContextType


class TestFeishuMessageText:
    """Text message parsing."""

    def test_text_message_basic(self):
        event = {
            "message": {
                "message_id": "om_xxx",
                "message_type": "text",
                "create_time": "1610000000",
                "content": '{"text": "hello world"}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.msg_id == "om_xxx"
        assert msg.ctype == ContextType.TEXT
        assert msg.content == "hello world"

    def test_text_message_with_spaces(self):
        event = {
            "message": {
                "message_id": "om_yyy",
                "message_type": "text",
                "create_time": "1610000001",
                "content": '{"text": "  hello  world  "}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.content == "hello  world"

    def test_text_message_empty(self):
        event = {
            "message": {
                "message_id": "om_empty",
                "message_type": "text",
                "create_time": "1610000002",
                "content": '{"text": ""}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.content == ""

    def test_text_message_group(self):
        event = {
            "message": {
                "message_id": "om_group",
                "message_type": "text",
                "create_time": "1610000003",
                "content": '{"text": "group chat"}',
            },
            "sender": {"sender_id": {"open_id": "ou_g"}},
        }
        msg = FeishuMessage(event, is_group=True)
        assert msg.is_group is True
        assert msg.content == "group chat"


class TestFeishuMessageInteractive:
    """Interactive (卡片) message parsing."""

    def test_interactive_title(self):
        event = {
            "message": {
                "message_id": "om_card",
                "message_type": "interactive",
                "create_time": "1610000100",
                "content": '{"title": "Click Me", "text": "body"}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.ctype == ContextType.TEXT
        assert msg.content == "Click Me"

    def test_interactive_text_fallback(self):
        event = {
            "message": {
                "message_id": "om_card2",
                "message_type": "interactive",
                "create_time": "1610000200",
                "content": '{"text": "fallback content"}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.content == "fallback content"

    def test_interactive_empty_content(self):
        event = {
            "message": {
                "message_id": "om_card3",
                "message_type": "interactive",
                "create_time": "1610000300",
                "content": "{}",
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.ctype == ContextType.TEXT
        # Should be empty or the JSON string


class TestFeishuMessageID:
    """Message ID extraction."""

    def test_msg_id(self):
        event = {
            "message": {
                "message_id": "om_abc123",
                "message_type": "text",
                "create_time": "1610000000",
                "content": '{"text": "x"}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.msg_id == "om_abc123"

    def test_create_time_string(self):
        event = {
            "message": {
                "message_id": "om_time",
                "message_type": "text",
                "create_time": "1700000000000",
                "content": '{"text": "x"}',
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
        msg = FeishuMessage(event)
        assert msg.create_time == "1700000000000"
