from models.bot_factory import create_bot
from bridge.bot_manager import resolve_bot_type
from bridge.context import Context
from bridge.reply import Reply
from common import const
from common.log import logger
from common.singleton import singleton
from config import conf
from translate.factory import create_translator
from voice.factory import create_voice


@singleton
class Bridge(object):
    def __init__(self):
        self.btype = {
            "chat": const.OPENAI,
            "voice_to_text": conf().get("voice_to_text", "openai"),
            "text_to_voice": conf().get("text_to_voice", "google"),
            "translate": conf().get("translate", "baidu"),
        }
        model_type = conf().get("model") or const.GPT_41_MINI
        if not isinstance(model_type, str):
            model_type = str(model_type)
        self.btype["chat"] = resolve_bot_type(model_type)

        self.bots = {}
        self.chat_bots = {}
        self._agent_bridge = None

    # 模型对应的接口
    def get_bot(self, typename):
        if self.bots.get(typename) is None:
            logger.info("create bot {} for {}".format(self.btype[typename], typename))
            if typename == "text_to_voice":
                self.bots[typename] = create_voice(self.btype[typename])
            elif typename == "voice_to_text":
                self.bots[typename] = create_voice(self.btype[typename])
            elif typename == "chat":
                self.bots[typename] = create_bot(self.btype[typename])
            elif typename == "translate":
                self.bots[typename] = create_translator(self.btype[typename])
        return self.bots[typename]

    def get_bot_type(self, typename):
        return self.btype[typename]

    def fetch_reply_content(self, query, context: Context) -> Reply:
        return self.get_bot("chat").reply(query, context)

    def fetch_voice_to_text(self, voiceFile) -> Reply:
        return self.get_bot("voice_to_text").voiceToText(voiceFile)

    def fetch_text_to_voice(self, text) -> Reply:
        return self.get_bot("text_to_voice").textToVoice(text)

    def fetch_translate(self, text, from_lang="", to_lang="en") -> Reply:
        return self.get_bot("translate").translate(text, from_lang, to_lang)

    def find_chat_bot(self, bot_type: str):
        if self.chat_bots.get(bot_type) is None:
            self.chat_bots[bot_type] = create_bot(bot_type)
        return self.chat_bots.get(bot_type)

    def reset_bot(self):
        """
        重置bot路由
        """
        self.__init__()

    def get_agent_bridge(self):
        """
        Get agent bridge for agent-based conversations
        """
        if self._agent_bridge is None:
            from bridge.agent_bridge import AgentBridge
            self._agent_bridge = AgentBridge(self)
        return self._agent_bridge

    def fetch_agent_reply(self, query: str, context: Context = None,
                          on_event=None, clear_history: bool = False) -> Reply:
        """
        Use super agent to handle the query

        Args:
            query: User query
            context: Context object
            on_event: Event callback for streaming
            clear_history: Whether to clear conversation history

        Returns:
            Reply object
        """
        agent_bridge = self.get_agent_bridge()
        return agent_bridge.agent_reply(query, context, on_event, clear_history)
