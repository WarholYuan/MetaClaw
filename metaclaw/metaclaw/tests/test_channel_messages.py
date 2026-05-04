"""
Tests for channel message classes: FeishuMessage, WeixinMessage, WecomBotMessage.
Tests message construction, type detection, content extraction.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bridge.context import ContextType
from channel.chat_message import ChatMessage


# ─────────────────── ChatMessage base class ───────────────────

def test_chat_message_creation():
    """ChatMessage can be created with raw message."""
    raw = {"key": "value"}
    msg = ChatMessage(raw)
    assert msg._rawmsg == raw
    assert msg.is_group is False
    assert msg.is_at is False


def test_chat_message_prepare_noop():
    """Prepare is a no-op when no _prepare_fn is set."""
    msg = ChatMessage({})
    msg.prepare()
    assert msg._prepared is False


def test_chat_message_prepare_with_fn():
    """Prepare calls the _prepare_fn."""
    called = []
    msg = ChatMessage({})

    def side_effect():
        called.append(True)

    msg._prepare_fn = side_effect
    msg.prepare()
    assert called == [True]
    # Calling again should be no-op
    msg.prepare()
    assert called == [True]


def test_chat_message_str():
    """String representation contains key fields."""
    msg = ChatMessage({})
    msg.msg_id = "msg-123"
    msg.create_time = 1234567890
    msg.ctype = ContextType.TEXT
    msg.content = "Hello"
    msg.from_user_id = "user1"
    msg.from_user_nickname = "User One"
    msg.to_user_id = "user2"
    msg.is_group = True
    msg.is_at = True

    s = str(msg)
    assert "msg-123" in s
    assert "Hello" in s
    assert "user1" in s
    assert "is_group=True" in s
    assert "is_at=True" in s


# ─────────────────── FeishuMessage tests ───────────────────

@pytest.fixture
def feishu_base_event():
    """Base Feishu event structure."""
    return {
        "message": {
            "message_id": "om_xxx123",
            "create_time": "1700000000000",
            "chat_id": "oc_yyy456",
        },
        "sender": {
            "sender_id": {
                "open_id": "ou_aaa111",
            }
        },
        "app_id": "app_zzz999",
    }


def test_feishu_text_message(feishu_base_event):
    """Feishu text message is parsed correctly."""
    event = feishu_base_event
    event["message"]["message_type"] = "text"
    event["message"]["content"] = json.dumps({"text": "Hello Feishu"})

    from channel.feishu.feishu_message import FeishuMessage
    msg = FeishuMessage(event)

    assert msg.ctype == ContextType.TEXT
    assert msg.content == "Hello Feishu"
    assert msg.msg_id == "om_xxx123"
    assert msg.from_user_id == "ou_aaa111"
    assert msg.to_user_id == "app_zzz999"
    assert msg.is_group is False


def test_feishu_text_message_group(feishu_base_event):
    """Feishu group text message strips @_user_1 mentions."""
    event = feishu_base_event
    event["message"]["message_type"] = "text"
    event["message"]["content"] = json.dumps({"text": "@_user_1 Hello group"})

    from channel.feishu.feishu_message import FeishuMessage
    msg = FeishuMessage(event, is_group=True)

    assert msg.is_group is True
    assert "@_user_1" not in msg.content
    assert "Hello group" in msg.content
    assert msg.other_user_id == "oc_yyy456"  # group chat_id
    assert msg.actual_user_id == "ou_aaa111"


def test_feishu_text_message_private(feishu_base_event):
    """Feishu private message sets other_user_id to sender."""
    event = feishu_base_event
    event["message"]["message_type"] = "text"
    event["message"]["content"] = json.dumps({"text": "Private hello"})

    from channel.feishu.feishu_message import FeishuMessage
    msg = FeishuMessage(event, is_group=False)

    assert msg.is_group is False
    assert msg.other_user_id == "ou_aaa111"  # sender in DM
    assert msg.actual_user_id == "ou_aaa111"


def test_feishu_interactive_message(feishu_base_event):
    """Feishu interactive (card) message is parsed as text."""
    event = feishu_base_event
    event["message"]["message_type"] = "interactive"
    event["message"]["content"] = json.dumps({"title": "Card Title", "text": "Card Text"})

    from channel.feishu.feishu_message import FeishuMessage
    msg = FeishuMessage(event)

    assert msg.ctype == ContextType.TEXT
    assert "Card Title" in msg.content


def test_feishu_interactive_no_title(feishu_base_event):
    """Interactive message without title falls back to text."""
    event = feishu_base_event
    event["message"]["message_type"] = "interactive"
    event["message"]["content"] = json.dumps({"text": "Just text"})

    from channel.feishu.feishu_message import FeishuMessage
    msg = FeishuMessage(event)

    assert msg.ctype == ContextType.TEXT
    assert "Just text" in msg.content


def test_feishu_post_text_only(feishu_base_event):
    """Feishu post (rich text) with only text elements."""
    event = feishu_base_event
    event["message"]["message_type"] = "post"
    event["message"]["content"] = json.dumps({
        "title": "Rich Post",
        "content": [
            [
                {"tag": "text", "text": "Paragraph 1 line 1"},
                {"tag": "text", "text": "Paragraph 1 line 2"},
            ],
            [
                {"tag": "text", "text": "Paragraph 2"},
            ]
        ]
    })

    from channel.feishu.feishu_message import FeishuMessage
    msg = FeishuMessage(event)

    assert msg.ctype == ContextType.TEXT
    assert "Rich Post" in msg.content
    assert "Paragraph 1 line 1" in msg.content
    assert "Paragraph 2" in msg.content


def test_feishu_unsupported_message_type(feishu_base_event):
    """Unsupported message type raises NotImplementedError."""
    event = feishu_base_event
    event["message"]["message_type"] = "sticker"

    from channel.feishu.feishu_message import FeishuMessage
    with pytest.raises(NotImplementedError, match="Unsupported"):
        FeishuMessage(event)


# ─────────────────── WeixinMessage tests ───────────────────

def test_weixin_text_message():
    """Weixin text message is parsed correctly."""
    from channel.weixin.weixin_message import WeixinMessage, ITEM_TEXT

    raw = {
        "message_id": "msg-wx-001",
        "create_time_ms": 1700000000000,
        "from_user_id": "wxuser001",
        "to_user_id": "wxbot001",
        "item_list": [
            {"type": ITEM_TEXT, "text_item": {"text": "Hello WeChat"}}
        ],
    }

    msg = WeixinMessage(raw)
    assert msg.ctype == ContextType.TEXT
    assert msg.content == "Hello WeChat"
    assert msg.from_user_id == "wxuser001"
    assert msg.is_group is False


def test_weixin_message_with_ref_text():
    """Weixin message with quoted reference."""
    from channel.weixin.weixin_message import WeixinMessage, ITEM_TEXT

    raw = {
        "message_id": "msg-wx-002",
        "create_time_ms": 1700000000000,
        "from_user_id": "wxuser002",
        "to_user_id": "wxbot002",
        "item_list": [
            {
                "type": ITEM_TEXT,
                "text_item": {"text": "What do you think?"},
                "ref_msg": {
                    "title": "Original Post Title",
                    "message_item": {
                        "type": ITEM_TEXT,
                        "text_item": {"text": "Original content"}
                    }
                }
            }
        ],
    }

    msg = WeixinMessage(raw)
    assert msg.ctype == ContextType.TEXT
    assert "[引用:" in msg.content
    assert "Original Post Title" in msg.content
    assert "What do you think?" in msg.content


def test_weixin_message_voice_with_transcription():
    """Weixin voice message with transcription is treated as text."""
    from channel.weixin.weixin_message import WeixinMessage, ITEM_VOICE

    raw = {
        "message_id": "msg-wx-003",
        "create_time_ms": 1700000000000,
        "from_user_id": "wxuser003",
        "to_user_id": "wxbot003",
        "item_list": [
            {"type": ITEM_VOICE, "voice_item": {"text": "语音转文字内容"}}
        ],
    }

    msg = WeixinMessage(raw)
    assert msg.ctype == ContextType.TEXT
    assert msg.content == "语音转文字内容"


def test_weixin_message_no_item_list():
    """Weixin message with empty item_list."""
    from channel.weixin.weixin_message import WeixinMessage

    raw = {
        "message_id": "msg-wx-004",
        "from_user_id": "wxuser004",
        "to_user_id": "wxbot004",
        "item_list": [],
    }

    msg = WeixinMessage(raw)
    assert msg.ctype == ContextType.TEXT
    assert msg.content == ""


def test_weixin_message_without_message_id():
    """Weixin message generates a fallback message_id."""
    from channel.weixin.weixin_message import WeixinMessage

    raw = {
        "from_user_id": "wxuser005",
        "to_user_id": "wxbot005",
        "item_list": [],
    }

    msg = WeixinMessage(raw)
    assert msg.msg_id is not None
    assert len(str(msg.msg_id)) > 0


# ─────────────────── WecomBotMessage tests ───────────────────

def test_wecom_text_message():
    """Wecom bot text message is parsed correctly."""
    from channel.wecom_bot.wecom_bot_message import WecomBotMessage

    raw = {
        "msgid": "wecom-msg-001",
        "create_time": 1700000000,
        "msgtype": "text",
        "from": {"userid": "user001"},
        "chatid": "chat001",
        "aibotid": "bot001",
        "text": {"content": "Hello WeCom"},
    }

    msg = WecomBotMessage(raw)
    assert msg.ctype == ContextType.TEXT
    assert msg.content == "Hello WeCom"
    assert msg.msg_id == "wecom-msg-001"
    assert msg.from_user_id == "user001"


def test_wecom_text_group_message():
    """Wecom bot group text strips @mentions."""
    from channel.wecom_bot.wecom_bot_message import WecomBotMessage

    raw = {
        "msgid": "wecom-msg-002",
        "create_time": 1700000000,
        "msgtype": "text",
        "from": {"userid": "user002"},
        "chatid": "chat002",
        "aibotid": "bot002",
        "text": {"content": "@bot_助手 帮我查一下天气"},
    }

    msg = WecomBotMessage(raw, is_group=True)
    assert msg.is_group is True
    assert msg.other_user_id == "chat002"
    assert "bot_助手" not in msg.content
    assert "帮我查一下天气" in msg.content


def test_wecom_voice_message():
    """Wecom bot voice message uses transcribed text content."""
    from channel.wecom_bot.wecom_bot_message import WecomBotMessage

    raw = {
        "msgid": "wecom-msg-003",
        "create_time": 1700000000,
        "msgtype": "voice",
        "from": {"userid": "user003"},
        "chatid": "chat003",
        "aibotid": "bot003",
        "voice": {"content": "语音转文字结果"},
    }

    msg = WecomBotMessage(raw)
    assert msg.ctype == ContextType.TEXT
    assert msg.content == "语音转文字结果"


def test_wecom_unsupported_type():
    """Wecom bot unsupported type raises NotImplementedError."""
    from channel.wecom_bot.wecom_bot_message import WecomBotMessage

    raw = {
        "msgid": "wecom-msg-004",
        "create_time": 1700000000,
        "msgtype": "unknown_type",
        "from": {"userid": "user004"},
        "chatid": "chat004",
        "aibotid": "bot004",
    }

    with pytest.raises(NotImplementedError, match="Unsupported"):
        WecomBotMessage(raw)


# ─────────────────── WecomBot _guess_ext_from_bytes ───────────────────

def test_guess_ext_png():
    """Magic bytes detection for PNG."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".png"


def test_guess_ext_jpg():
    """Magic bytes detection for JPG."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"\xff\xd8\xff" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".jpg"


def test_guess_ext_pdf():
    """Magic bytes detection for PDF."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"%PDF" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".pdf"


def test_guess_ext_gif():
    """Magic bytes detection for GIF."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"GIF89a" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".gif"


def test_guess_ext_zip():
    """Magic bytes detection for ZIP."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"PK\x03\x04" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".zip"


def test_guess_ext_docx():
    """Office ZIP files (docx) are detected."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"PK\x03\x04" + b"\x00" * 100 + b"word/" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".docx"


def test_guess_ext_xlsx():
    """Office ZIP files (xlsx) are detected."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"PK\x03\x04" + b"\x00" * 100 + b"xl/" + b"\x00" * 100
    assert _guess_ext_from_bytes(data) == ".xlsx"


def test_guess_ext_empty():
    """Empty data returns empty string."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    assert _guess_ext_from_bytes(b"") == ""
    assert _guess_ext_from_bytes(b"ab") == ""


def test_guess_ext_unknown():
    """Unknown magic bytes return empty string."""
    from channel.wecom_bot.wecom_bot_message import _guess_ext_from_bytes
    data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
    assert _guess_ext_from_bytes(data) == ""
