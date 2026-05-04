"""CLI entry point."""

import os
import subprocess
import sys

import click
from cli import __version__
from cli.commands.skill import skill
from cli.commands.process import start, stop, restart, update, status, logs
from cli.commands.context import context
from cli.commands.install import install_browser
from cli.commands.knowledge import knowledge
from cli.commands.lark import lark
from cli.commands.doctor import doctor_group
from common.brand import APP_NAME, CLI_NAME


HELP_TEXT = f"""Usage: {CLI_NAME} COMMAND [ARGS]...

  {APP_NAME} CLI - Manage your {APP_NAME} instance.

Commands:
  help     Show this message.
  version  Show the version.
  start    Start {APP_NAME}.
  stop     Stop {APP_NAME}.
  restart  Restart {APP_NAME}.
  update   Update {APP_NAME} to a version and restart.
  status   Show {APP_NAME} running status.
  logs     View {APP_NAME} logs.
  doctor   Manage Metadoctor (health monitor).
  setup    Run the interactive configuration wizard.
  skill    Manage {APP_NAME} skills.
  knowledge  Manage knowledge base.
  lark     Feishu (Lark) operations via lark-cli.
  install-browser  Install browser tool (Playwright + Chromium).

Tip: You can also send /help, /skill list, etc. in agent chat."""


class MetaClawCLI(click.Group):

    def format_help(self, ctx, formatter):
        formatter.write(HELP_TEXT.strip())
        formatter.write("\n")

    def parse_args(self, ctx, args):
        if args and args[0] == 'help':
            click.echo(HELP_TEXT.strip())
            ctx.exit(0)
        return super().parse_args(ctx, args)


@click.group(cls=MetaClawCLI, invoke_without_command=True, context_settings=dict(help_option_names=[]))
@click.pass_context
def main(ctx):
    """CLI - Manage your agent instance."""
    if ctx.invoked_subcommand is None:
        click.echo(HELP_TEXT.strip())


@main.command()
def version():
    """Show the version."""
    click.echo(f"{CLI_NAME} {__version__}")


@main.command(name='help')
@click.pass_context
def help_cmd(ctx):
    """Show this message."""
    click.echo(HELP_TEXT.strip())


@main.command()
def setup():
    """Run the interactive configuration wizard."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.abspath(os.path.join(project_root, os.pardir, os.pardir))
    script = os.path.join(repo_root, "scripts", "setup.sh")
    if not os.path.exists(script):
        raise click.ClickException(f"setup script not found: {script}")
    raise SystemExit(subprocess.call(["bash", script], env=os.environ.copy()))


main.add_command(skill)
main.add_command(start)
main.add_command(stop)
main.add_command(restart)
main.add_command(update)
main.add_command(status)
main.add_command(logs)
main.add_command(context)
main.add_command(knowledge)
main.add_command(lark)
main.add_command(doctor_group)
main.add_command(install_browser)
main.add_command(setup)


if __name__ == '__main__':
    main()
