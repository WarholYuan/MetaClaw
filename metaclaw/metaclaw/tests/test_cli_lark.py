import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from click.testing import CliRunner
from cli.commands.lark import lark


def test_lark_group_help():
    runner = CliRunner()
    result = runner.invoke(lark, ['--help'])
    assert result.exit_code == 0
    assert 'Feishu' in result.output or 'Lark' in result.output


def test_lark_send_help():
    runner = CliRunner()
    result = runner.invoke(lark, ['send', '--help'])
    assert result.exit_code == 0
    assert 'user' in result.output.lower()
    assert 'message' in result.output.lower()


def test_lark_agenda_help():
    runner = CliRunner()
    result = runner.invoke(lark, ['agenda', '--help'])
    assert result.exit_code == 0


def test_lark_search_user_help():
    runner = CliRunner()
    result = runner.invoke(lark, ['search-user', '--help'])
    assert result.exit_code == 0
    assert 'query' in result.output.lower()


def test_lark_api_help():
    runner = CliRunner()
    result = runner.invoke(lark, ['api', '--help'])
    assert result.exit_code == 0
    assert 'method' in result.output.lower()
    assert 'path' in result.output.lower()


def test_send_command_constructs_correct_args():
    from unittest.mock import patch, MagicMock
    runner = CliRunner()
    with patch('cli.commands.lark.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='sent', stderr='')
        result = runner.invoke(lark, ['send', 'user123', 'hello world'])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'lark-cli'
        assert 'im' in args
        assert 'message' in args
        assert 'create' in args
        assert '--receive_id' in args
        assert 'user123' in args
        assert '--content' in args
        # Verify content is valid JSON with the message
        content_arg = args[args.index('--content') + 1]
        import json
        parsed = json.loads(content_arg)
        assert parsed['text'] == 'hello world'


def test_agenda_command_constructs_correct_args():
    from unittest.mock import patch, MagicMock
    import datetime
    runner = CliRunner()
    with patch('cli.commands.lark.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='[]', stderr='')
        result = runner.invoke(lark, ['agenda'])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'lark-cli'
        assert 'calendar' in args
        assert 'event' in args
        assert 'list' in args
        assert '--start_date' in args
        assert '--end_date' in args
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        assert today in args


def test_search_user_command_constructs_correct_args():
    from unittest.mock import patch, MagicMock
    runner = CliRunner()
    with patch('cli.commands.lark.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='[]', stderr='')
        result = runner.invoke(lark, ['search-user', 'zhangsan'])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'lark-cli'
        assert 'contact' in args
        assert 'user' in args
        assert 'search' in args
        assert '--query' in args
        assert 'zhangsan' in args
        assert '--limit' in args
        assert '20' in args


def test_api_command_constructs_correct_args():
    from unittest.mock import patch, MagicMock
    runner = CliRunner()
    with patch('cli.commands.lark.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='{}', stderr='')
        result = runner.invoke(lark, ['api', 'GET', '/open-apis/contact/v3/users', '--query', 'page_size=50'])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'lark-cli'
        assert 'api' in args
        assert 'GET' in args
        assert '/open-apis/contact/v3/users' in args
        assert '--query' in args
        assert 'page_size=50' in args


def test_api_command_with_body():
    from unittest.mock import patch, MagicMock
    runner = CliRunner()
    with patch('cli.commands.lark.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='{}', stderr='')
        result = runner.invoke(lark, ['api', 'POST', '/open-apis/im/v1/messages', '--body', '{"text":"hi"}'])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'POST' in args
        assert '--body' in args
        assert '{"text":"hi"}' in args
