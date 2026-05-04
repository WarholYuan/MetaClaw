import os
import json
from config import pconf, plugin_config, conf, write_plugin_config
from common.brand import DEFAULT_AGENT_WORKSPACE
from common.log import logger
from common.utils import expand_path


def get_plugin_config_path(plugin_name: str) -> str:
    workspace = expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE))
    config_dir = os.path.join(workspace, "plugin-configs")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, f"{plugin_name.lower()}.json")


class Plugin:
    def __init__(self):
        self.handlers = {}

    def load_config(self) -> dict:
        """
        加载当前插件配置
        :return: 插件配置字典
        """
        # 优先获取 plugins/config.json 中的全局配置
        plugin_conf = pconf(self.name)
        if not plugin_conf:
            # 全局配置不存在，则获取插件目录下的配置
            plugin_config_path = get_plugin_config_path(self.name)
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)
            else:
                legacy_plugin_config_path = os.path.join(self.path, "config.json")
                if os.path.exists(legacy_plugin_config_path):
                    with open(legacy_plugin_config_path, "r", encoding="utf-8") as f:
                        plugin_conf = json.load(f)

                # 写入全局配置内存
            if plugin_conf:
                write_plugin_config({self.name: plugin_conf})
        return plugin_conf

    def save_config(self, config: dict):
        try:
            write_plugin_config({self.name: config})
            # 写入全局配置
            workspace = expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE))
            global_config_path = os.path.join(workspace, "plugin-configs", "config.json")
            if os.path.exists(global_config_path):
                with open(global_config_path, "w", encoding='utf-8') as f:
                    json.dump(plugin_config, f, indent=4, ensure_ascii=False)
            # 写入插件配置
            plugin_config_path = get_plugin_config_path(self.name)
            with open(plugin_config_path, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logger.warn("save plugin config failed: {}".format(e))

    def get_help_text(self, **kwargs):
        return "暂无帮助信息"

    def reload(self):
        pass
