# encoding:utf-8

from common.brand import DEFAULT_APPDATA_DIR, DEFAULT_WEIXIN_CREDENTIALS_PATH

# 通道相关配置项
CHANNEL_SETTINGS = {
    # Bot触发配置
    "single_chat_prefix": ["bot", "@bot"],  # 私聊时文本需要包含该前缀才能触发机器人回复
    "single_chat_reply_prefix": "",  # 私聊时自动回复的前缀
    "single_chat_reply_suffix": "",  # 私聊时自动回复的后缀，\n 可以换行
    "group_chat_prefix": ["@bot"],  # 群聊时包含该前缀则会触发机器人回复
    "no_need_at": False,  # 群聊回复时是否不需要艾特
    "group_chat_reply_prefix": "",  # 群聊时自动回复的前缀
    "group_chat_reply_suffix": "",  # 群聊时自动回复的后缀，\n 可以换行
    "group_chat_keyword": [],  # 群聊时包含该关键词则会触发机器人回复
    "group_at_off": False,  # 是否关闭群聊时@bot的触发
    "group_name_white_list": ["ChatGPT测试群", "ChatGPT测试群2"],  # 开启自动回复的群名称列表
    "group_name_keyword_white_list": [],  # 开启自动回复的群名称关键词列表
    "group_chat_in_one_session": ["ChatGPT测试群"],  # 支持会话上下文共享的群名称
    "group_shared_session": False,  # 群聊是否共享会话上下文（所有成员共享）。False时每个用户在群内有独立会话
    "nick_name_black_list": [],  # 用户昵称黑名单
    "group_welcome_msg": "",  # 配置新人进群固定欢迎语，不配置则使用随机风格欢迎
    "trigger_by_self": False,  # 是否允许机器人触发
    "group_chat_exit_group": False,
    # 服务时间限制
    "chat_time_module": False,  # 是否开启服务时间限制
    "chat_start_time": "00:00",  # 服务开始时间
    "chat_stop_time": "24:00",  # 服务结束时间
    # wechatmp的配置
    "wechatmp_token": "",  # 微信公众平台的Token
    "wechatmp_port": 8080,  # 微信公众平台的端口,需要端口转发到80或443
    "wechatmp_app_id": "",  # 微信公众平台的appID
    "wechatmp_app_secret": "",  # 微信公众平台的appsecret
    "wechatmp_aes_key": "",  # 微信公众平台的EncodingAESKey，加密模式需要
    # wechatcom的通用配置
    "wechatcom_corp_id": "",  # 企业微信公司的corpID
    # wechatcomapp的配置
    "wechatcomapp_token": "",  # 企业微信app的token
    "wechatcomapp_port": 9898,  # 企业微信app的服务端口,不需要端口转发
    "wechatcomapp_secret": "",  # 企业微信app的secret
    "wechatcomapp_agent_id": "",  # 企业微信app的agent_id
    "wechatcomapp_aes_key": "",  # 企业微信app的aes_key
    # 飞书配置
    "feishu_port": 80,  # 飞书bot监听端口
    "feishu_app_id": "",  # 飞书机器人应用APP Id
    "feishu_app_secret": "",  # 飞书机器人APP secret
    "feishu_token": "",  # 飞书 verification token
    "feishu_bot_name": "",  # 飞书机器人的名字
    "feishu_event_mode": "websocket",  # 飞书事件接收模式: webhook(HTTP服务器) 或 websocket(长连接)
    "feishu_request_timeout_seconds": 1800,  # 飞书单条消息最大等待时间，超时后释放会话队列
    "feishu_heartbeat_interval_seconds": 20,  # 飞书长任务卡片心跳更新时间，设为0关闭
    "feishu_fast_reply_threshold_seconds": 5,  # 该时间内完成的飞书回复保持简洁展示
    "feishu_detail_expand_threshold_seconds": 10,  # 超过该时间后展开工具/思考等细节
    "feishu_reasoning_summary_chars": 260,  # 飞书卡片底部思考摘要最大字数
    "feishu_question_preview_chars": 360,  # 飞书卡片顶部原消息预览最大字数
    "feishu_answer_card_chars": 3600,  # 飞书单张回复卡片正文最大展示字数，超出会自动分卡片发送
    "feishu_footer_card_chars": 1600,  # 飞书卡片底部工具/状态最大展示字数
    "feishu_long_answer_notice_threshold": 3600,  # 超过该长度时在卡片内提示内容较长
    # 钉钉配置
    "dingtalk_client_id": "",  # 钉钉机器人Client ID
    "dingtalk_client_secret": "",  # 钉钉机器人Client Secret
    "dingtalk_card_enabled": False,
    # 企微智能机器人配置(长连接模式)
    "wecom_bot_id": "",  # 企微智能机器人BotID
    "wecom_bot_secret": "",  # 企微智能机器人长连接Secret
    # 微信配置
    "weixin_token": "",  # 微信登录后获取的bot_token，留空则启动时自动扫码登录
    "weixin_base_url": "https://i" + "l" + "ink" + "ai.weixin.qq.com",  # Weixin API base URL
    "weixin_cdn_base_url": "https://novac2c.cdn.weixin.qq.com/c2c",  # CDN base URL
    "weixin_credentials_path": DEFAULT_WEIXIN_CREDENTIALS_PATH,  # credentials file path
    # chatgpt指令自定义触发词
    "clear_memory_commands": ["#清除记忆"],  # 重置会话指令，必须以#开头
    # channel配置
    "channel_type": "",  # 通道类型，支持多渠道同时运行。单个: "feishu"，多个: "feishu, dingtalk" 或 ["feishu", "dingtalk"]。可选值: web,feishu,dingtalk,wecom_bot,weixin,wechatmp,wechatmp_service,wechatcom_app
    "web_console": True,  # 是否自动启动Web控制台（默认启动）。设为False可禁用
    "subscribe_msg": "",  # 订阅消息, 支持: wechatmp, wechatmp_service, wechatcom_app
    "debug": False,  # 是否开启debug模式，开启后会打印更多日志
    "appdata_dir": DEFAULT_APPDATA_DIR,  # 数据目录，默认放在用户工作区，不污染程序目录
    "service_log_file": "",  # CLI 后台服务 stdout/stderr 日志文件；留空则使用工作区 logs/nohup.out
    # 插件配置
    "plugin_trigger_prefix": "$",  # 规范插件提供聊天相关指令的前缀，建议不要和管理员指令前缀"#"冲突
    # 是否使用全局插件配置
    "use_global_plugin_config": False,
    "max_media_send_count": 3,  # 单次最大发送媒体资源的个数
    "media_send_interval": 1,  # 发送图片的事件间隔，单位秒
    "web_host": "127.0.0.1",  # Web console bind host, default local-only for safer exposure
    "web_port": 9899,
    "web_password": "",  # Web console password; empty means no authentication required
    "web_session_expire_days": 30,  # Auth session expiry in days
    "cloud_server_url": "",  # 云服务端地址，非空时自动进入 cloud_mode，API 请求转发到该地址
    "amap_worker_url": "",  # AMap 服务地址，留空则禁用 amap_nearby_poi tool
    "amap_worker_secret": "",  # AMap 服务鉴权密钥
}
