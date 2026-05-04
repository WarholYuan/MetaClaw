# encoding:utf-8

import copy
import ast
import json
import logging
import os
import pickle

from common.brand import DEFAULT_AGENT_WORKSPACE, DEFAULT_APPDATA_DIR, DEFAULT_WEIXIN_CREDENTIALS_PATH
from common.log import logger

from .models import MODEL_SETTINGS
from .channel import CHANNEL_SETTINGS

# 将所有可用的配置项写在字典里, 请使用小写字母
# 此处的配置值无实际意义，程序不会读取此处的配置，仅用于提示格式，请将配置加入到config.json中
available_setting = {}
available_setting.update(MODEL_SETTINGS)
available_setting.update(CHANNEL_SETTINGS)


class Config(dict):
    """
    Configuration dictionary with dot-notation attribute access.
    
    Usage:
        conf().open_ai_api_key          # preferred: dot notation
        conf().get("open_ai_api_key")   # backward-compat: dict-style
    
    Unknown keys raise AttributeError to catch typos early,
    unlike dict.get() which silently returns None.
    """
    def __init__(self, d=None):
        super().__init__()
        if d is None:
            d = {}
        for k, v in d.items():
            self[k] = v
        # user_datas: 用户数据，key为用户名，value为用户数据，也是dict
        self.user_datas = {}

    def __getattr__(self, key):
        """Dot-notation access: conf().open_ai_api_key"""
        if key.startswith("_") or key in ("user_datas",):
            return super().__getattribute__(key)
        if key in self:
            return self[key]
        if key in available_setting:
            return available_setting[key]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{key}'")

    def __getitem__(self, key):
        # 跳过以下划线开头的注释字段
        if not key.startswith("_") and key not in available_setting:
            logger.warning(f"[Config] key '{key}' not in available_setting, may not take effect")
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        # 跳过以下划线开头的注释字段
        if not key.startswith("_") and key not in available_setting:
            logger.warning(f"[Config] key '{key}' not in available_setting, may not take effect")
        return super().__setitem__(key, value)

    def get(self, key, default=None):
        # 跳过以下划线开头的注释字段
        if key.startswith("_"):
            return super().get(key, default)
        
        # 如果key不在available_setting中，直接返回default
        if key not in available_setting:
            return super().get(key, default)
        
        try:
            return self[key]
        except KeyError as e:
            if default is not None:
                return default
            return available_setting.get(key)
        except Exception as e:
            raise e

    # Make sure to return a dictionary to ensure atomic
    def get_user_data(self, user) -> dict:
        if self.user_datas.get(user) is None:
            self.user_datas[user] = {}
        return self.user_datas[user]

    def load_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "rb") as f:
                self.user_datas = pickle.load(f)
                logger.debug("[Config] User datas loaded.")
        except FileNotFoundError as e:
            logger.debug("[Config] User datas file not found, ignore.")
        except Exception as e:
            logger.warning(f"[Config] User datas error: {e}")
            self.user_datas = {}

    def save_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "wb") as f:
                pickle.dump(self.user_datas, f)
                logger.info("[Config] User datas saved.")
        except Exception as e:
            logger.info(f"[Config] User datas error: {e}")


def get_writable_config_path() -> str:
    """Resolve the config file path to write updates to.

    Preference:
    1. METACLAW_CONFIG_FILE (explicit override)
    2. Existing workspace config
    3. Existing project config
    4. Workspace config (create on first write)
    """
    env_path = os.environ.get("METACLAW_CONFIG_FILE", "").strip()
    if env_path:
        return os.path.expanduser(env_path)

    workspace_config = os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "config.json"))
    if os.path.exists(workspace_config):
        return workspace_config

    project_config = "./config.json"
    if os.path.exists(project_config):
        return project_config

    return workspace_config


config = Config()


def drag_sensitive(config):
    try:
        if isinstance(config, str):
            conf_dict: dict = json.loads(config)
            conf_dict_copy = copy.deepcopy(conf_dict)
            for key in conf_dict_copy:
                if "key" in key or "secret" in key:
                    if isinstance(conf_dict_copy[key], str):
                        conf_dict_copy[key] = conf_dict_copy[key][0:3] + "*" * 5 + conf_dict_copy[key][-3:]
            return json.dumps(conf_dict_copy, indent=4)

        elif isinstance(config, dict):
            config_copy = copy.deepcopy(config)
            for key in config:
                if "key" in key or "secret" in key:
                    if isinstance(config_copy[key], str):
                        config_copy[key] = config_copy[key][0:3] + "*" * 5 + config_copy[key][-3:]
            return config_copy
    except Exception as e:
        logger.exception(e)
        return config
    return config


def _is_sensitive_key(key: str) -> bool:
    key = str(key).lower()
    return any(mark in key for mark in ("key", "secret", "token", "password", "pwd"))


def _parse_env_override_value(raw_value: str, default_value):
    raw_value = str(raw_value)
    lower = raw_value.strip().lower()

    # Keep string-like settings as-is (e.g. model names, URLs, prompts).
    if isinstance(default_value, str):
        return raw_value

    # Bool parsing with common env forms.
    if isinstance(default_value, bool):
        if lower in ("true", "1", "yes", "on"):
            return True
        if lower in ("false", "0", "no", "off"):
            return False
        return raw_value

    try:
        parsed = ast.literal_eval(raw_value)
    except Exception:
        parsed = raw_value

    if isinstance(default_value, int) and not isinstance(default_value, bool):
        return parsed if isinstance(parsed, int) else raw_value
    if isinstance(default_value, float):
        return parsed if isinstance(parsed, (int, float)) else raw_value
    if isinstance(default_value, list):
        return parsed if isinstance(parsed, list) else raw_value
    if isinstance(default_value, dict):
        return parsed if isinstance(parsed, dict) else raw_value
    if isinstance(default_value, tuple):
        return parsed if isinstance(parsed, tuple) else raw_value
    if default_value is None:
        if lower in ("none", "null", ""):
            return None
        return parsed

    return raw_value


def _format_env_override_log(key: str, value) -> str:
    if _is_sensitive_key(key):
        rendered = "*****"
    else:
        rendered = str(value)
        if len(rendered) > 120:
            rendered = rendered[:117] + "..."
    return f"[INIT] override config by environ args: {key}={rendered}"


def get_config_path() -> str:
    """Resolve the active config file path.

    Precedence:
    1. METACLAW_CONFIG_FILE
    2. ~/metaclaw/config.json
    3. ./config.json
    4. ../config.json
    5. ./config-template.json
    """
    env_path = os.environ.get("METACLAW_CONFIG_FILE", "").strip()
    if env_path:
        return os.path.expanduser(env_path)

    workspace_config = os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "config.json"))
    if os.path.exists(workspace_config):
        return workspace_config

    project_config = "./config.json"
    if os.path.exists(project_config):
        return project_config

    parent_project_config = os.path.abspath(os.path.join(os.getcwd(), "..", "config.json"))
    if os.path.exists(parent_project_config):
        return parent_project_config

    return "./config-template.json"


def load_config():
    global config

    # 打印 ASCII Logo
    logger.info(" __  __      _        ____ _                 ")
    logger.info("|  \\/  | ___| |_ __ _/ ___| | __ ___      __")
    logger.info("| |\\/| |/ _ \\ __/ _` | |   | |/ _` \\ \\ /\\ / /")
    logger.info("| |  | |  __/ || (_| | |___| | (_| |\\ V  V / ")
    logger.info("|_|  |_|\\___|\\__\\__,_|\\____|_|\\__,_| \\_/\\_/  ")
    logger.info("")
    config_path = get_config_path()
    if os.path.basename(config_path) == "config-template.json":
        logger.info("配置文件不存在，将使用config-template.json模板")

    config_str = read_file(config_path)
    logger.debug(f"[INIT] config str: {drag_sensitive(config_str)}")
    file_config = json.loads(config_str)

    # Support partial config files written by the web console by layering them
    # on top of the template defaults instead of treating them as complete config.
    if os.path.basename(config_path) != "config-template.json":
        template_path = "./config-template.json"
        if os.path.exists(template_path):
            try:
                template_config = json.loads(read_file(template_path))
                template_config.update(file_config)
                file_config = template_config
            except Exception as e:
                logger.warning(f"[Config] Failed to merge config-template defaults: {e}")

    for key, value in available_setting.items():
        if key not in file_config:
            file_config[key] = copy.deepcopy(value)

    # 将json字符串反序列化为dict类型
    config = Config(file_config)

    # Brand defaults and legacy value migration.
    if "agent_workspace" not in config:
        config["agent_workspace"] = DEFAULT_AGENT_WORKSPACE
    if "appdata_dir" not in config:
        config["appdata_dir"] = DEFAULT_APPDATA_DIR
    if "weixin_credentials_path" not in config:
        config["weixin_credentials_path"] = DEFAULT_WEIXIN_CREDENTIALS_PATH
    if config.get("agent_workspace") == "~/metaclaw":
        config["agent_workspace"] = DEFAULT_AGENT_WORKSPACE
    if config.get("appdata_dir") == "":
        config["appdata_dir"] = DEFAULT_APPDATA_DIR
    if config.get("weixin_credentials_path") == "~/.weixin_metaclaw_credentials.json":
        config["weixin_credentials_path"] = DEFAULT_WEIXIN_CREDENTIALS_PATH

    # override config with environment variables.
    # Some online deployment platforms (e.g. Railway) deploy project from github directly. So you shouldn't put your secrets like api key in a config file, instead use environment variables to override the default config.
    for name, value in os.environ.items():
        name = name.lower()
        # 跳过以下划线开头的注释字段
        if name.startswith("_"):
            continue
        if name in available_setting:
            parsed_value = _parse_env_override_value(value, available_setting.get(name))
            config[name] = parsed_value
            logger.info(_format_env_override_log(name, parsed_value))

    if config.get("debug", False):
        logger.setLevel(logging.DEBUG)
        logger.debug("[INIT] set log level to DEBUG")

    logger.info(f"[INIT] load config: {drag_sensitive(config)}")

    # 打印系统初始化信息
    logger.info("[INIT] ========================================")
    logger.info("[INIT] System Initialization")
    logger.info("[INIT] ========================================")
    logger.info(f"[INIT] Channel: {config.get('channel_type', 'unknown')}")
    logger.info(f"[INIT] Model: {config.get('model', 'unknown')}")

    # Agent模式信息
    if config.get("agent", False):
        workspace = config.get("agent_workspace", DEFAULT_AGENT_WORKSPACE)
        logger.info(f"[INIT] Mode: Agent (workspace: {workspace})")
    else:
        logger.info("[INIT] Mode: Chat (在config.json中设置 \"agent\":true 可启用Agent模式)")

    logger.info(f"[INIT] Debug: {config.get('debug', False)}")
    logger.info("[INIT] ========================================")

    # Sync selected config values to environment variables so that
    # subprocesses (e.g. shell skill scripts) can access them directly.
    # Existing env vars are NOT overwritten (env takes precedence).
    _CONFIG_TO_ENV = {
        "open_ai_api_key": "OPENAI_API_KEY",
        "open_ai_api_base": "OPENAI_API_BASE",
        "claude_api_key": "CLAUDE_API_KEY",
        "claude_api_base": "CLAUDE_API_BASE",
        "gemini_api_key": "GEMINI_API_KEY",
        "gemini_api_base": "GEMINI_API_BASE",
        "minimax_api_key": "MINIMAX_API_KEY",
        "minimax_api_base": "MINIMAX_API_BASE",
        "zhipu_ai_api_key": "ZHIPU_AI_API_KEY",
        "zhipu_ai_api_base": "ZHIPU_AI_API_BASE",
        "moonshot_api_key": "MOONSHOT_API_KEY",
        "moonshot_api_base": "MOONSHOT_API_BASE",
        "ark_api_key": "ARK_API_KEY",
        "ark_api_base": "ARK_API_BASE",
        "dashscope_api_key": "DASHSCOPE_API_KEY",
        "dashscope_api_base": "DASHSCOPE_API_BASE",
        # Channel credentials (used by skills that check env vars)
        "feishu_app_id": "FEISHU_APP_ID",
        "feishu_app_secret": "FEISHU_APP_SECRET",
        "dingtalk_client_id": "DINGTALK_CLIENT_ID",
        "dingtalk_client_secret": "DINGTALK_CLIENT_SECRET",
        "wechatmp_app_id": "WECHATMP_APP_ID",
        "wechatmp_app_secret": "WECHATMP_APP_SECRET",
        "wechatcomapp_agent_id": "WECHATCOMAPP_AGENT_ID",
        "wechatcomapp_secret": "WECHATCOMAPP_SECRET",
        "qq_app_id": "QQ_APP_ID",
        "qq_app_secret": "QQ_APP_SECRET",
        "weixin_token": "WEIXIN_TOKEN",
        "metadoctor_feishu_app_id": "METADOCTOR_FEISHU_APP_ID",
        "metadoctor_feishu_app_secret": "METADOCTOR_FEISHU_APP_SECRET",
    }
    injected = 0
    for conf_key, env_key in _CONFIG_TO_ENV.items():
        if env_key not in os.environ:
            val = config.get(conf_key, "")
            if val:
                os.environ[env_key] = str(val)
                injected += 1

    injected += _sync_skill_config_to_env(config.get("skill", {}))

    if injected:
        logger.info(f"[INIT] Synced {injected} config values to environment variables")

    config.load_user_datas()


def _sync_skill_config_to_env(skill_section) -> int:
    """Flatten skill-namespaced config into environment variables.

    Mapping rule: ``config["skill"][<name>][<key>]`` -> ``SKILL_<NAME>_<KEY>``
    (e.g. ``skill["image-generation"].model`` -> ``SKILL_IMAGE_GENERATION_MODEL``).

    This lets subprocess-based skill scripts read their own settings without
    importing project code. Existing env vars are NOT overwritten so the
    real environment always wins.

    Returns the number of variables actually injected.
    """
    if not isinstance(skill_section, dict):
        return 0
    injected = 0
    for skill_name, skill_conf in skill_section.items():
        if not isinstance(skill_conf, dict):
            continue
        name_part = str(skill_name).replace("-", "_").upper()
        for key, val in skill_conf.items():
            if val is None or val == "":
                continue
            env_key = f"SKILL_{name_part}_{str(key).upper()}"
            if env_key in os.environ:
                continue
            os.environ[env_key] = str(val)
            injected += 1
    return injected


def get_root():
    return os.path.dirname(os.path.abspath(__file__))


def read_file(path):
    with open(path, mode="r", encoding="utf-8-sig") as f:
        return f.read()


def conf():
    return config


def get_appdata_dir():
    configured = conf().get("appdata_dir", DEFAULT_APPDATA_DIR)
    configured = DEFAULT_APPDATA_DIR if configured == "" else configured
    configured = os.path.expanduser(configured)
    data_path = configured if os.path.isabs(configured) else os.path.join(get_root(), configured)
    if not os.path.exists(data_path):
        logger.info(f"[INIT] data path not exists, create it: {data_path}")
        os.makedirs(data_path)
    return data_path


def subscribe_msg():
    trigger_prefix = conf().get("single_chat_prefix", [""])[0]
    msg = conf().get("subscribe_msg", "")
    return msg.format(trigger_prefix=trigger_prefix)


# global plugin config
plugin_config = {}


def write_plugin_config(pconf: dict):
    """
    写入插件全局配置
    :param pconf: 全量插件配置
    """
    global plugin_config
    for k in pconf:
        plugin_config[k.lower()] = pconf[k]

def remove_plugin_config(name: str):
    """
    移除待重新加载的插件全局配置
    :param name: 待重载的插件名
    """
    global plugin_config
    plugin_config.pop(name.lower(), None)


def pconf(plugin_name: str) -> dict:
    """
    根据插件名称获取配置
    :param plugin_name: 插件名称
    :return: 该插件的配置项
    """
    return plugin_config.get(plugin_name.lower())


# 全局配置，用于存放全局生效的状态
global_config = {"admin_users": []}
