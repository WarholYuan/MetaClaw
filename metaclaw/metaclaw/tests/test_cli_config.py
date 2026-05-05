import json

from cli import utils


def test_cli_load_config_json_prefers_env_override(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"agent_workspace": str(tmp_path / "workspace")}), encoding="utf-8")
    monkeypatch.setenv("METACLAW_CONFIG_FILE", str(config_path))

    assert utils.load_config_json()["agent_workspace"] == str(tmp_path / "workspace")


def test_service_log_file_empty_config_falls_back_to_workspace_logs(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"agent_workspace": str(workspace), "service_log_file": ""}),
        encoding="utf-8",
    )
    monkeypatch.setenv("METACLAW_CONFIG_FILE", str(config_path))

    assert utils.get_service_log_file() == str(workspace / "logs" / "nohup.out")
