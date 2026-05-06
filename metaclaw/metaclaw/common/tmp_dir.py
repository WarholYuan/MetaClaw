import os
import pathlib

from common.brand import DEFAULT_AGENT_WORKSPACE
from common.utils import expand_path
from config import conf


class TmpDir(object):
    """A temporary directory that is deleted when the object is destroyed."""

    def __init__(self):
        workspace_root = expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE))
        self.tmpFilePath = pathlib.Path(workspace_root) / "tmp"
        pathExists = os.path.exists(self.tmpFilePath)
        if not pathExists:
            os.makedirs(self.tmpFilePath)

    def path(self):
        return str(self.tmpFilePath) + "/"
