import hashlib
import os
import shutil

from common.brand import DEFAULT_AGENT_WORKSPACE
from common.utils import expand_path
from config import conf


def _session_dir(session_id: str) -> str:
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    workspace_root = expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE))
    return os.path.join(workspace_root, "tmp", h)


def get_session_tmp_dir(session_id: str) -> str:
    """创建并返回会话专属 tmp 目录路径。"""
    path = _session_dir(session_id)
    os.makedirs(path, exist_ok=True)
    return path


def cleanup_session_tmp(session_id: str):
    """删除会话 tmp 目录及其所有内容。"""
    path = _session_dir(session_id)
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
