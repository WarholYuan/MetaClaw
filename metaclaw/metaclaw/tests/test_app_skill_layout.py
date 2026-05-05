import inspect

import app


def test_app_does_not_sync_builtin_skills_into_workspace():
    source = inspect.getsource(app)

    assert "_sync_builtin_skills" not in source
    assert "copytree" not in source
    assert "rmtree" not in source
