from bridge.context import ContextType
from channel.chat_message import ChatMessage
import json
import os
import requests
from common.log import logger
from common.brand import DEFAULT_AGENT_WORKSPACE
from common.tmp_dir import TmpDir
from common import utils
from common.utils import expand_path
from config import conf

def _safe_json_parse(raw_value, fallback=None):
    """Safely parse JSON, returning fallback on failure."""
    if not raw_value:
        return fallback if fallback is not None else {}
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"[FeiShu] JSON parse error: {e} | raw={str(raw_value)[:200]}")
        return fallback if fallback is not None else {}

def _safe_http_get(url, headers, params=None, timeout=30):
    """Safely perform HTTP GET, returning (response_or_None, error_message)."""
    try:
        response = requests.get(url=url, headers=headers, params=params, timeout=timeout)
        return response, None
    except requests.exceptions.Timeout:
        return None, f"Timeout after {timeout}s"
    except requests.exceptions.ConnectionError:
        return None, "Connection failed"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"


class FeishuMessage(ChatMessage):
    def __init__(self, event: dict, is_group=False, access_token=None):
        super().__init__(event)
        msg = event.get("message")
        sender = event.get("sender")
        self.access_token = access_token
        self.msg_id = msg.get("message_id")
        self.create_time = msg.get("create_time")
        self.is_group = is_group
        msg_type = msg.get("message_type")

        if msg_type == "text":
            self.ctype = ContextType.TEXT
            content = _safe_json_parse(msg.get('content'))
            self.content = content.get("text", "").strip()
        elif msg_type == "interactive":
            self.ctype = ContextType.TEXT
            content = _safe_json_parse(msg.get("content"), fallback={})
            self.content = content.get("title") or content.get("text") or json.dumps(content, ensure_ascii=False)
        elif msg_type == "image":
            # 单张图片消息：下载并缓存，等待用户提问时一起发送
            self.ctype = ContextType.IMAGE
            content = _safe_json_parse(msg.get("content"))
            image_key = content.get("image_key")
            if not image_key:
                logger.error("[FeiShu] No image_key in image message")
                self.content = "[图片解析失败: 无 image_key]"
                self.image_path = None
                self.from_user_id = sender.get("sender_id", {}).get("open_id")
                self.to_user_id = event.get("app_id")
                return
            
            # 下载图片到工作空间临时目录
            workspace_root = expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE))
            tmp_dir = os.path.join(workspace_root, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            image_path = os.path.join(tmp_dir, f"{image_key}.png")
            
            # 下载图片
            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg.get('message_id')}/resources/{image_key}"
            headers = {"Authorization": "Bearer " + access_token}
            params = {"type": "image"}
            response, error = _safe_http_get(url, headers, params, timeout=30)
            
            if response and response.status_code == 200:
                with open(image_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"[FeiShu] Downloaded single image, key={image_key}, path={image_path}")
                self.content = image_path
                self.image_path = image_path  # 保存图片路径
            else:
                status_info = f"status={response.status_code}" if response else "N/A"
                logger.error(f"[FeiShu] Failed to download single image, key={image_key}, error={error or status_info}")
                self.content = f"[图片下载失败: {image_key}]"
                self.image_path = None
        elif msg_type == "post":
            # 富文本消息，可能包含图片、文本等多种元素
            content = _safe_json_parse(msg.get("content"))
            
            # 飞书富文本消息结构：content 直接包含 title 和 content 数组
            # 不是嵌套在 post 字段下
            title = content.get("title", "")
            content_list = content.get("content", [])
            
            logger.info(f"[FeiShu] Post message - title: '{title}', content_list length: {len(content_list)}")
            
            # 收集所有图片和文本
            image_keys = []
            text_parts = []
            
            if title:
                text_parts.append(title)
            
            for block in content_list:
                logger.debug(f"[FeiShu] Processing block: {block}")
                # block 本身就是元素列表
                if not isinstance(block, list):
                    continue
                    
                for element in block:
                    element_tag = element.get("tag")
                    logger.debug(f"[FeiShu] Element tag: {element_tag}, element: {element}")
                    if element_tag == "img":
                        # 找到图片元素
                        image_key = element.get("image_key")
                        if image_key:
                            image_keys.append(image_key)
                    elif element_tag == "text":
                        # 文本元素
                        text_content = element.get("text", "")
                        if text_content:
                            text_parts.append(text_content)
            
            logger.info(f"[FeiShu] Parsed - images: {len(image_keys)}, text_parts: {text_parts}")
            
            # 富文本消息统一作为文本消息处理
            self.ctype = ContextType.TEXT
            
            if image_keys:
                # 如果包含图片，下载并在文本中引用本地路径
                workspace_root = expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE))
                tmp_dir = os.path.join(workspace_root, "tmp")
                os.makedirs(tmp_dir, exist_ok=True)
                
                # 保存图片路径映射
                self.image_paths = {}
                for image_key in image_keys:
                    image_path = os.path.join(tmp_dir, f"{image_key}.png")
                    self.image_paths[image_key] = image_path
                
                def _download_images():
                    for image_key, image_path in self.image_paths.items():
                        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{self.msg_id}/resources/{image_key}"
                        headers = {"Authorization": "Bearer " + access_token}
                        params = {"type": "image"}
                        response, error = _safe_http_get(url, headers, params, timeout=30)
                        if response and response.status_code == 200:
                            with open(image_path, "wb") as f:
                                f.write(response.content)
                            logger.info(f"[FeiShu] Image downloaded from post message, key={image_key}, path={image_path}")
                        else:
                            status_info = f"status={response.status_code}" if response else "N/A"
                            logger.error(f"[FeiShu] Failed to download image from post, key={image_key}, error={error or status_info}")
                
                # 立即下载图片，不使用延迟下载
                # 因为 TEXT 类型消息不会调用 prepare()
                _download_images()
                
                # 构建消息内容：文本 + 图片路径
                content_parts = []
                if text_parts:
                    content_parts.append("\n".join(text_parts).strip())
                for image_key, image_path in self.image_paths.items():
                    content_parts.append(f"[图片: {image_path}]")
                
                self.content = "\n".join(content_parts)
                logger.info(f"[FeiShu] Received post message with {len(image_keys)} image(s) and text: {self.content}")
            else:
                # 纯文本富文本消息
                self.content = "\n".join(text_parts).strip() if text_parts else "[富文本消息]"
                logger.info(f"[FeiShu] Received post message (text only): {self.content}")
        elif msg_type == "file":
            self.ctype = ContextType.FILE
            content = _safe_json_parse(msg.get("content"))
            file_key = content.get("file_key")
            file_name = content.get("file_name", "unknown")

            self.content = TmpDir().path() + file_key + "." + utils.get_path_suffix(file_name)

            def _download_file():
                # 如果响应状态码是200，则将响应内容写入本地文件
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{self.msg_id}/resources/{file_key}"
                headers = {
                    "Authorization": "Bearer " + access_token,
                }
                params = {
                    "type": "file"
                }
                response, error = _safe_http_get(url, headers, params, timeout=30)
                if response and response.status_code == 200:
                    with open(self.content, "wb") as f:
                        f.write(response.content)
                else:
                    status_info = f"status={response.status_code}" if response else "N/A"
                    logger.info(f"[FeiShu] Failed to download file, key={file_key}, error={error or status_info}")
            self._prepare_fn = _download_file
        else:
            raise NotImplementedError("Unsupported message type: Type:{} ".format(msg_type))

        self.from_user_id = sender.get("sender_id").get("open_id")
        self.to_user_id = event.get("app_id")
        if is_group:
            # 群聊
            self.other_user_id = msg.get("chat_id")
            self.actual_user_id = self.from_user_id
            self.content = self.content.replace("@_user_1", "").strip()
            self.actual_user_nickname = ""
        else:
            # 私聊
            self.other_user_id = self.from_user_id
            self.actual_user_id = self.from_user_id
