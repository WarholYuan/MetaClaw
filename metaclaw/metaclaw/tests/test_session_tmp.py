import os


def _set_workspace(monkeypatch, tmp_path):
    from config import conf
    workspace = tmp_path / "workspace"
    monkeypatch.setitem(conf(), "agent_workspace", str(workspace))
    return workspace


def test_get_session_tmp_dir_creates_dir(monkeypatch, tmp_path):
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    workspace = _set_workspace(monkeypatch, tmp_path)
    session_id = "test_user_001"
    path = get_session_tmp_dir(session_id)
    try:
        assert os.path.isdir(path)
        assert path.startswith(str(workspace / "tmp") + os.sep)
        assert len(os.path.basename(path)) == 8  # sha256前8位
    finally:
        cleanup_session_tmp(session_id)


def test_get_session_tmp_dir_same_id_same_path(monkeypatch, tmp_path):
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    _set_workspace(monkeypatch, tmp_path)
    session_id = "test_user_002"
    path1 = get_session_tmp_dir(session_id)
    path2 = get_session_tmp_dir(session_id)
    try:
        assert path1 == path2
    finally:
        cleanup_session_tmp(session_id)


def test_get_session_tmp_dir_different_ids_different_paths(monkeypatch, tmp_path):
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    _set_workspace(monkeypatch, tmp_path)
    path1 = get_session_tmp_dir("user:group_a")
    path2 = get_session_tmp_dir("user:group_b")
    try:
        assert path1 != path2
    finally:
        cleanup_session_tmp("user:group_a")
        cleanup_session_tmp("user:group_b")


def test_cleanup_session_tmp_removes_dir(monkeypatch, tmp_path):
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    _set_workspace(monkeypatch, tmp_path)
    session_id = "test_user_003"
    path = get_session_tmp_dir(session_id)
    assert os.path.isdir(path)
    cleanup_session_tmp(session_id)
    assert not os.path.exists(path)


def test_cleanup_session_tmp_nonexistent_is_noop(monkeypatch, tmp_path):
    from common.session_tmp import cleanup_session_tmp
    _set_workspace(monkeypatch, tmp_path)
    # 不存在的 session，不应抛异常
    cleanup_session_tmp("nonexistent_session_xyz")


def test_tmp_dir_uses_workspace_tmp(monkeypatch, tmp_path):
    from common.tmp_dir import TmpDir
    workspace = _set_workspace(monkeypatch, tmp_path)

    path = TmpDir().path()

    assert path == str(workspace / "tmp") + os.sep
    assert os.path.isdir(path)
