# Troubleshooting

## `metaclaw` command not found

The Python scripts directory is not on `PATH`.

```bash
python3 -m pip show metaclaw
python3 -m site --user-base
```

Add the matching `bin` directory to `PATH`, then open a new shell.

## Python Version Too Old

Use Python 3.10 or newer:

```bash
python3 --version
```

If your system Python is old, install a newer Python with pyenv, Homebrew, or the official installer.

## Package Download Is Slow

Use a China mirror:

```bash
python3 -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
python3 -m pip install --upgrade metaclaw
```

## Provider Authentication Fails

Check that the expected key is present:

```bash
grep -E 'DEEPSEEK_API_KEY|DOUBAO_API_KEY|ARK_API_KEY|MOONSHOT_API_KEY|OPENAI_API_KEY' ~/.metaclaw/.env
```

Then check the service status and logs:

```bash
metaclaw status
metaclaw logs
```

## Web Console Cannot Open

Check host, port, and local firewall rules:

```json
{
  "web_host": "127.0.0.1",
  "web_port": 9899
}
```

If another process owns the port, change `web_port` and restart MetaClaw.

## Upgrade Migration Fails

Back up the config, then run migrations directly:

```bash
cp -a ~/.metaclaw/config.json ~/.metaclaw/config.json.bak
metaclaw upgrade --migrations-only
```

If JSON parsing fails, validate the file:

```bash
python3 -m json.tool ~/.metaclaw/config.json >/dev/null
```
