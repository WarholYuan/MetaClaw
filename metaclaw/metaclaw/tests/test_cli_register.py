import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from click.testing import CliRunner
from cli.cli import main


def test_lark_command_registered():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert 'lark' in result.output, f"'lark' not in help output: {result.output}"
