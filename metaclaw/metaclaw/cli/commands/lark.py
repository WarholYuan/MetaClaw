"""lark - Feishu (Lark) CLI commands via lark-cli."""

import datetime
import json
import subprocess
import sys
import click


def _run_lark_cli(*args):
    """Run lark-cli with the given arguments."""
    cmd = ["lark-cli"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result
    except FileNotFoundError:
        click.echo(
            "Error: lark-cli not found. Install it with:\n"
            "  npm install -g @larksuite/cli\n"
            "Or ensure it is in your PATH.",
            err=True,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        click.echo("Error: lark-cli command timed out after 30s.", err=True)
        sys.exit(1)


@click.group()
def lark():
    """Feishu (Lark) operations via lark-cli."""
    pass


@lark.command()
@click.argument("user")
@click.argument("message")
@click.option(
    "--type",
    "msg_type",
    default="text",
    help="Message type: text, post, image, interactive, etc.",
)
def send(user, message, msg_type):
    """Send a message to a Feishu user."""
    content = json.dumps({"text": message})
    result = _run_lark_cli(
        "im", "message", "create",
        "--receive_id_type", "open_id",
        "--receive_id", user,
        "--msg_type", msg_type,
        "--content", content,
    )
    if result.returncode != 0:
        click.echo(f"Error: {result.stderr}", err=True)
        sys.exit(1)
    click.echo(result.stdout)


@lark.command()
def agenda():
    """Show today's calendar events."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    result = _run_lark_cli(
        "calendar", "event", "list",
        "--start_date", today,
        "--end_date", today,
    )
    if result.returncode != 0:
        click.echo(f"Error: {result.stderr}", err=True)
        sys.exit(1)
    click.echo(result.stdout)


@lark.command("search-user")
@click.argument("query")
@click.option("--limit", "-l", default=20, help="Maximum number of results")
def search_user(query, limit):
    """Search for Feishu users."""
    result = _run_lark_cli(
        "contact", "user", "search",
        "--query", query,
        "--limit", str(limit),
    )
    if result.returncode != 0:
        click.echo(f"Error: {result.stderr}", err=True)
        sys.exit(1)
    click.echo(result.stdout)


@lark.command()
@click.argument("method")
@click.argument("path")
@click.option("--body", "-b", default="", help="Request body (JSON string)")
@click.option("--query", "-q", default="", help="Query parameters (key=value,comma-separated)")
def api(method, path, body, query):
    """Make a raw API call to Feishu. METHOD: GET, POST, PUT, DELETE, PATCH."""
    args = ["api", method.upper(), path]
    if body:
        args.extend(["--body", body])
    if query:
        args.extend(["--query", query])
    result = _run_lark_cli(*args)
    if result.returncode != 0:
        click.echo(f"Error: {result.stderr}", err=True)
        sys.exit(1)
    click.echo(result.stdout)
