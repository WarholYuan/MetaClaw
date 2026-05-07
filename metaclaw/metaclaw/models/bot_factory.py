"""
channel factory
"""
from common import const
from config import conf


_PROVIDER_KEY_REQUIREMENTS = {
    const.DEEPSEEK: ("deepseek_api_key", "DEEPSEEK_API_KEY"),
    const.DOUBAO: ("ark_api_key", "DOUBAO_API_KEY"),
    const.MOONSHOT: ("moonshot_api_key", "MOONSHOT_API_KEY"),
    const.OPENAI: ("open_ai_api_key", "OPENAI_API_KEY"),
    const.CHATGPT: ("open_ai_api_key", "OPENAI_API_KEY"),
    const.OPEN_AI: ("open_ai_api_key", "OPENAI_API_KEY"),
}


def _normalize_bot_type(bot_type):
    normalized = str(bot_type or "").strip().lower()
    aliases = {
        "deepseek": const.DEEPSEEK,
        "doubao": const.DOUBAO,
        "moonshot": const.MOONSHOT,
        "kimi": const.MOONSHOT,
        "openai": const.OPENAI,
        "open_ai": const.OPENAI,
        "chatgpt": const.OPENAI,
    }
    return aliases.get(normalized, bot_type)


def _require_provider_api_key(bot_type):
    requirement = _PROVIDER_KEY_REQUIREMENTS.get(bot_type)
    if not requirement:
        return
    conf_key, env_key = requirement
    if not conf().get(conf_key):
        raise RuntimeError(f"Set {env_key} in ~/.metaclaw/.env")


def create_bot(bot_type):
    """
    create a bot_type instance
    :param bot_type: bot type code
    :return: bot instance
    """
    bot_type = _normalize_bot_type(bot_type)
    _require_provider_api_key(bot_type)

    if bot_type == const.BAIDU:
        # 替换Baidu Unit为Baidu文心千帆对话接口
        # from models.baidu.baidu_unit_bot import BaiduUnitBot
        # return BaiduUnitBot()
        from models.baidu.baidu_wenxin import BaiduWenxinBot
        return BaiduWenxinBot()

    elif bot_type == const.DEEPSEEK:
        from models.deepseek.deepseek_bot import DeepSeekBot
        return DeepSeekBot()

    elif bot_type in (const.OPENAI, const.CHATGPT, const.CUSTOM):  # OpenAI-compatible API
        from models.chatgpt.chat_gpt_bot import ChatGPTBot
        return ChatGPTBot()

    elif bot_type == const.OPEN_AI:
        # OpenAI 官方对话模型API
        from models.openai.open_ai_bot import OpenAIBot
        return OpenAIBot()

    elif bot_type == const.CHATGPTONAZURE:
        # Azure chatgpt service https://azure.microsoft.com/en-in/products/cognitive-services/openai-service/
        from models.chatgpt.chat_gpt_bot import AzureChatGPTBot
        return AzureChatGPTBot()

    elif bot_type == const.XUNFEI:
        from models.xunfei.xunfei_spark_bot import XunFeiBot
        return XunFeiBot()

    elif bot_type == const.CLAUDEAPI:
        from models.claudeapi.claude_api_bot import ClaudeAPIBot
        return ClaudeAPIBot()
    elif bot_type in (const.QWEN, const.QWEN_DASHSCOPE):
        from models.dashscope.dashscope_bot import DashscopeBot
        return DashscopeBot()
    elif bot_type == const.GEMINI:
        from models.gemini.google_gemini_bot import GoogleGeminiBot
        return GoogleGeminiBot()

    elif bot_type == const.ZHIPU_AI or bot_type == "glm-4":  # "glm-4" kept for backward compatibility
        from models.zhipuai.zhipuai_bot import ZHIPUAIBot
        return ZHIPUAIBot()

    elif bot_type == const.MOONSHOT:
        from models.moonshot.moonshot_bot import MoonshotBot
        return MoonshotBot()
    
    elif bot_type == const.MiniMax:
        from models.minimax.minimax_bot import MinimaxBot
        return MinimaxBot()

    elif bot_type == const.MODELSCOPE:
        from models.modelscope.modelscope_bot import ModelScopeBot
        return ModelScopeBot()

    elif bot_type == const.DOUBAO:
        from models.doubao.doubao_bot import DoubaoBot
        return DoubaoBot()

    raise RuntimeError


# Bot types that natively support tool/function calling.
# Agent layer uses this to decide whether to wrap a bot with ToolCallingBotAdapter.
_TOOL_CALLING_BOT_TYPES = {
    const.OPENAI, const.CHATGPT, const.CUSTOM,   # OpenAI-compatible
    const.DEEPSEEK,                               # OpenAI-compatible
    const.DOUBAO,                                 # OpenAI-compatible
    const.MOONSHOT,                               # OpenAI-compatible
    const.MiniMax,                                # OpenAI-compatible
    const.MODELSCOPE,                             # OpenAI-compatible
    const.QWEN_DASHSCOPE, const.QWEN,             # DashScope (supports tools)
    const.GEMINI,                                 # Native function calling
    const.CLAUDEAPI,                              # Native tool use
    const.ZHIPU_AI,                               # Native function calling
    const.CHATGPTONAZURE,                         # Azure OpenAI
}


def supports_tools(bot_type: str) -> bool:
    """
    Return True if bots of this type natively support tool/function calling.
    
    Used by AgentBridge to skip the ToolCallingBotAdapter wrapper for bots
    that already have native tool support.
    """
    return bot_type in _TOOL_CALLING_BOT_TYPES
