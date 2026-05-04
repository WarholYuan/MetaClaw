"""
Shared model routing — single source of truth for resolving bot_type from model name.

Used by both bridge.Bridge (legacy routing) and bridge.agent_bridge.AgentLLMModel (agent routing).
"""
import logging
from common import const

logger = logging.getLogger(__name__)


def resolve_bot_type(model_name: str, *, use_azure: bool = False) -> str:
    """
    Resolve the bot_type string from a model name.

    Combines the logic previously duplicated between bridge.py (Bridge.__init__)
    and agent_bridge.py (AgentLLMModel._resolve_bot_type).

    Priority:
    1. Explicit bot_type config (bot_type key in config.json)
    2. Special legacy models (text-davinci-003, Azure)
    3. Exact model name matches
    4. Prefix matches (gemini→GEMINI, claude→CLAUDEAPI, etc.)
    5. Default: OPENAI

    Returns a const key like OPENAI, DEEPSEEK, GEMINI, etc.
    """
    from config import conf

    # User-configured explicit bot_type takes priority
    configured = conf().get("bot_type")
    if configured:
        return configured

    if not model_name or not isinstance(model_name, str):
        return const.OPENAI

    # Legacy special cases
    if model_name in ["text-davinci-003"]:
        return const.OPEN_AI
    if use_azure or conf().get("use_azure_chatgpt", False):
        return const.CHATGPTONAZURE

    # Exact model name matches (no prefix ambiguity)
    _EXACT_MAP = {
        "wenxin": const.BAIDU,
        "wenxin-4": const.BAIDU,
        "xunfei": const.XUNFEI,
        const.QWEN: const.QWEN_DASHSCOPE,
        const.MODELSCOPE: const.MODELSCOPE,
    }
    if model_name in _EXACT_MAP:
        return _EXACT_MAP[model_name]

    # Qwen turbo/plus/max variants
    if model_name in [const.QWEN_TURBO, const.QWEN_PLUS, const.QWEN_MAX]:
        return const.QWEN_DASHSCOPE

    # Moonshot / Kimi
    if model_name in [const.MOONSHOT, "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]:
        return const.MOONSHOT

    # MiniMax
    if model_name.lower().startswith("minimax") or model_name in ["abab6.5-chat"]:
        return const.MiniMax

    # Prefix matching for modern models
    _PREFIX_MAP = [
        ("qwen", const.QWEN_DASHSCOPE),
        ("qwq", const.QWEN_DASHSCOPE),
        ("qvq", const.QWEN_DASHSCOPE),
        ("gemini", const.GEMINI),
        ("glm", const.ZHIPU_AI),
        ("claude", const.CLAUDEAPI),
        ("moonshot", const.MOONSHOT),
        ("kimi", const.MOONSHOT),
        ("doubao", const.DOUBAO),
        ("deepseek", const.DEEPSEEK),
    ]
    for prefix, btype in _PREFIX_MAP:
        if model_name.startswith(prefix):
            return btype

    return const.OPENAI
