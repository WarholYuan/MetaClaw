import json
import os
from common.log import logger
from common.singleton import singleton
from config import get_appdata_dir

PERMISSION_BLOCKED = "blocked"
PERMISSION_NORMAL = "normal"
PERMISSION_ADMIN = "admin"

PERMISSION_LABELS = {
    PERMISSION_BLOCKED: "已阻止",
    PERMISSION_NORMAL: "普通用户",
    PERMISSION_ADMIN: "管理员",
}

PERMISSION_TOOLS = {
    "bash": "Bash 命令",
    "read": "读取文件",
    "write": "写入文件",
    "edit": "编辑文件",
}


@singleton
class UserManager:
    def __init__(self):
        self._data_path = os.path.join(get_appdata_dir(), "users.json")
        self._users = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._data_path):
                with open(self._data_path, "r", encoding="utf-8") as f:
                    self._users = json.load(f)
                logger.debug("[UserManager] Users loaded.")
        except Exception as e:
            logger.warning(f"[UserManager] Load error: {e}")
            self._users = {}

    def _save(self):
        try:
            with open(self._data_path, "w", encoding="utf-8") as f:
                json.dump(self._users, f, ensure_ascii=False, indent=2)
            logger.debug("[UserManager] Users saved.")
        except Exception as e:
            logger.warning(f"[UserManager] Save error: {e}")

    def register(self, open_id, name=None):
        if open_id not in self._users:
            self._users[open_id] = {
                "open_id": open_id,
                "name": name or open_id,
                "permission": PERMISSION_NORMAL,
                "tools": list(PERMISSION_TOOLS.keys()),
            }
            self._save()
        elif name and self._users[open_id].get("name") != name:
            self._users[open_id]["name"] = name
            self._save()

    def get_permission(self, open_id):
        user = self._users.get(open_id)
        if user is None:
            return PERMISSION_NORMAL
        return user.get("permission", PERMISSION_NORMAL)

    def list_users(self):
        return list(self._users.values())

    def update_user(self, open_id, body):
        user = self._users.get(open_id)
        if user is None:
            return False
        user.update(body)
        self._save()
        return True

    def delete_user(self, open_id):
        if open_id in self._users:
            del self._users[open_id]
            self._save()
            return True
        return False

    def get_allowed_skills(self, open_id):
        """Return list of allowed skill names for a user, or None for all."""
        user = self._users.get(open_id)
        if user is None:
            return None
        return user.get("skills", None)

    def get_allowed_tools(self, open_id):
        """Return list of allowed tool names for a user, or None for all."""
        user = self._users.get(open_id)
        if user is None:
            return None
        return user.get("tools", None)
