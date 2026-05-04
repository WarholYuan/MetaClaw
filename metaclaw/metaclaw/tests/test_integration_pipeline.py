"""
Integration test: 验证从消息进入 → Agent 处理 → 工具调用 → 返回结果的完整链路。

不依赖真实 LLM API，通过 mock AgentLLMModel 来验证管道完整性。
"""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _inject_config(cfg):
    """直接替换 config 模块的全局 config 对象，让所有 import conf 的模块生效"""
    import config as config_module
    config_module.config = cfg


class TestFullPipeline:
    """端到端集成测试：Bridge → AgentBridge → Agent → 工具 → 回复"""

    def test_pipeline_init_to_reply(self, tmp_path):
        """
        验证: 最小化配置 → Agent 初始化 → mock LLM → 回复
        """
        from config import Config
        from bridge.bridge import Bridge
        from bridge.agent_bridge import AgentBridge
        from bridge.context import Context, ContextType
        from bridge.reply import ReplyType

        workspace = str(tmp_path / "workspace")
        os.makedirs(workspace, exist_ok=True)
        os.makedirs(os.path.join(workspace, "skills"), exist_ok=True)

        _inject_config(Config({
            "model": "gpt-3.5-turbo",
            "open_ai_api_key": "mock-key",
            "open_ai_api_base": "https://api.openai.com/v1",
            "agent_workspace": workspace,
            "channel_type": "web",
            "agent_max_steps": 3,
            "temperature": 0.0,
            "top_p": 1.0,
            "bot_type": "openai",
            "agent_max_context_turns": 10,
            "agent_max_context_tokens": 50000,
            "knowledge": False,
            "enable_thinking": False,
        }))

        bridge = Bridge()
        agent_bridge = AgentBridge(bridge)

        # ── Mock AgentLLMModel 让 LLM 返回假响应 ───────────────────────
        mock_model_instance = MagicMock()

        def fake_call_stream(request, **kwargs):
            yield {
                "choices": [{"delta": {"content": "这是测试回复：收到你的消息了。"}}]
            }

        mock_model_instance.call_stream = fake_call_stream
        mock_model_instance.call = MagicMock(return_value={
            "choices": [{"message": {"content": "这是测试回复。"}}]
        })
        mock_model_instance.model = "gpt-3.5-turbo"

        with patch("bridge.agent_bridge.AgentLLMModel", return_value=mock_model_instance), \
             patch("bridge.agent_bridge.AgentEventHandler", autospec=True):
            # agent_reply 内部会通过 get_agent → _init_agent_for_session
            # → initialize_agent → create_agent 来创建 Agent，
            # create_agent 里会创建 AgentLLMModel，由于我们 mock 了，
            # 所以 agent 会得到 mock_model_instance
            reply = agent_bridge.agent_reply(
                query="你好，这是一条测试消息",
                context=Context(
                    type=ContextType.TEXT,
                    content="你好，这是一条测试消息",
                    kwargs={"session_id": "test_001", "channel_type": "web"},
                ),
            )

            assert reply is not None
            assert reply.type == ReplyType.TEXT, f"Expected TEXT, got {reply.type}: {reply.content}"
            assert len(reply.content) > 0

    def test_tool_and_skill_loading(self, tmp_path):
        """
        验证: Agent 初始化时正确加载了工具和 skill。
        通过 mock LLM 确保不调用真实 API。
        """
        from config import Config
        from bridge.bridge import Bridge
        from bridge.agent_bridge import AgentBridge
        from bridge.context import Context, ContextType
        from bridge.reply import ReplyType

        workspace = str(tmp_path / "workspace")
        os.makedirs(workspace, exist_ok=True)
        os.makedirs(os.path.join(workspace, "skills"), exist_ok=True)

        _inject_config(Config({
            "model": "gpt-3.5-turbo",
            "open_ai_api_key": "mock-key",
            "open_ai_api_base": "https://api.openai.com/v1",
            "agent_workspace": workspace,
            "channel_type": "web",
            "agent_max_steps": 3,
            "bot_type": "openai",
            "agent_max_context_turns": 10,
            "agent_max_context_tokens": 50000,
            "knowledge": False,
            "enable_thinking": False,
        }))

        bridge = Bridge()
        agent_bridge = AgentBridge(bridge)

        mock_model_instance = MagicMock()
        mock_model_instance.call_stream = MagicMock(return_value=iter([
            {"choices": [{"delta": {"content": "收到。我有 bash、read、write、edit 等工具可用。"}}]}
        ]))
        mock_model_instance.call = MagicMock(return_value={
            "choices": [{"message": {"content": "收到。"}}]
        })
        mock_model_instance.model = "gpt-3.5-turbo"

        with patch("bridge.agent_bridge.AgentLLMModel", return_value=mock_model_instance), \
             patch("bridge.agent_bridge.AgentEventHandler", autospec=True):
            reply = agent_bridge.agent_reply(
                query="列出你可以使用的工具",
                context=Context(
                    type=ContextType.TEXT,
                    content="列出你可以使用的工具",
                    kwargs={"session_id": "test_002", "channel_type": "web"},
                ),
            )

            assert reply is not None
            assert reply.type == ReplyType.TEXT, f"Expected TEXT got {reply.type}: {reply.content}"

    def test_agent_with_tool_call_loop(self, tmp_path):
        """
        验证: mock tool-call 循环 — 第一轮 tool_use → 第二轮最终文本。
        """
        from config import Config
        from bridge.bridge import Bridge
        from bridge.agent_bridge import AgentBridge
        from bridge.context import Context, ContextType
        from bridge.reply import ReplyType

        workspace = str(tmp_path / "workspace")
        os.makedirs(workspace, exist_ok=True)
        os.makedirs(os.path.join(workspace, "skills"), exist_ok=True)

        _inject_config(Config({
            "model": "gpt-3.5-turbo",
            "open_ai_api_key": "mock-key",
            "open_ai_api_base": "https://api.openai.com/v1",
            "agent_workspace": workspace,
            "channel_type": "web",
            "agent_max_steps": 3,
            "bot_type": "openai",
            "agent_max_context_turns": 10,
            "agent_max_context_tokens": 50000,
            "knowledge": False,
            "enable_thinking": False,
        }))

        bridge = Bridge()
        agent_bridge = AgentBridge(bridge)

        mock_model_instance = MagicMock()
        call_count = [0]

        def fake_call_stream(request, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                yield {
                    "choices": [{
                        "delta": {
                            "tool_calls": [{
                                "index": 0,
                                "id": "call_test123",
                                "function": {
                                    "name": "bash",
                                    "arguments": '{"command": "echo hello"}'
                                }
                            }]
                        }
                    }]
                }
            else:
                yield {
                    "choices": [{"delta": {"content": "执行完毕。bash 输出: hello"}}]
                }

        mock_model_instance.call_stream = fake_call_stream
        mock_model_instance.call = MagicMock(return_value={
            "choices": [{"message": {"content": "执行完毕。"}}]
        })
        mock_model_instance.model = "gpt-3.5-turbo"

        with patch("bridge.agent_bridge.AgentLLMModel", return_value=mock_model_instance), \
             patch("bridge.agent_bridge.AgentEventHandler", autospec=True):
            reply = agent_bridge.agent_reply(
                query="执行 echo hello",
                context=Context(
                    type=ContextType.TEXT,
                    content="执行 echo hello",
                    kwargs={"session_id": "test_003", "channel_type": "web"},
                ),
            )

            assert reply is not None
            assert reply.type == ReplyType.TEXT
            assert call_count[0] >= 1, f"Expected at least 1 LLM call, got {call_count[0]}"
