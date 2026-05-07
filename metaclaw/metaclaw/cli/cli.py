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
from common.brand import APP_NAME, CLI_NAME, DEFAULT_ENV_FILE
from config.migrations import MigrationError, run_pending_migrations


HELP_TEXT = f"""Usage: {CLI_NAME} COMMAND [ARGS]...

  {APP_NAME} CLI - Manage your {APP_NAME} instance.

Commands:
  help     Show this message.
  version  Show the version.
  init     Initialize local MetaClaw configuration.
  start    Start {APP_NAME}.
  run      Run {APP_NAME}.
  stop     Stop {APP_NAME}.
  restart  Restart {APP_NAME}.
  update   Update {APP_NAME} to a version and restart.
  upgrade  Upgrade {APP_NAME} to a version and restart.
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


@click.group(cls=MetaClawCLI, invoke_without_command=True, context_settings=dict(help_option_names=["--help", "-h"]))
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


@main.command()
def init():
    """Initialize local MetaClaw configuration."""
    env_file = os.path.expanduser(DEFAULT_ENV_FILE)
    env_dir = os.path.dirname(env_file)
    os.makedirs(env_dir, exist_ok=True)

    template_keys = [
        "DEEPSEEK_API_KEY",
        "DOUBAO_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENAI_API_KEY",
    ]

    existing = ""
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            existing = f.read()

    lines = []
    for key in template_keys:
        if f"{key}=" not in existing:
            lines.append(f"{key}=")

    if lines:
        mode = "a" if existing else "w"
        with open(env_file, mode, encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines))
            f.write("\n")

    click.echo(f"{APP_NAME} initialized: {env_file}")


@main.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground (don't daemonize)")
@click.option("--no-logs", is_flag=True, help="Don't tail logs after starting")
@click.pass_context
def run(ctx, foreground, no_logs):
    """Run MetaClaw."""
    ctx.invoke(start, foreground=foreground, no_logs=no_logs)


@main.command()
@click.argument("version", required=False)
@click.option("--force", is_flag=True, help="Allow upgrade with local source changes")
@click.option("--migrations-only", is_flag=True, help="Only run pending config migrations")
@click.pass_context
def upgrade(ctx, version, force, migrations_only):
    """Upgrade and restart MetaClaw."""
    try:
        applied = run_pending_migrations()
    except MigrationError as exc:
        raise click.ClickException(str(exc)) from exc

    if applied:
        click.echo(f"Applied config migrations: {', '.join(applied)}")
    else:
        click.echo("No pending config migrations.")

    if migrations_only:
        return

    ctx.invoke(update, version=version, force=force)


main.add_command(skill)
main.add_command(start)
main.add_command(stop)
main.add_command(restart)
main.add_command(update)
main.add_command(status)
main.add_command(logs)
main.add_command(run)
main.add_command(context)
main.add_command(knowledge)
main.add_command(lark)
main.add_command(doctor_group)
main.add_command(install_browser)
main.add_command(setup)


if __name__ == '__main__':
    main()
