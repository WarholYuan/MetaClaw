# MetaClaw Upgrade

Use this guide for PyPI-installed MetaClaw deployments.

## Back Up

The upgrade script backs up the main config and memory directory:

```bash
bash scripts/upgrade.sh
```

Manual backup:

```bash
mkdir -p ~/.metaclaw/backups/manual-$(date +%Y%m%d%H%M%S)
cp -a ~/.metaclaw/config.json ~/.metaclaw/backups/manual-$(date +%Y%m%d%H%M%S)/ 2>/dev/null || true
cp -a ~/.metaclaw/workspace/memory ~/.metaclaw/backups/manual-$(date +%Y%m%d%H%M%S)/ 2>/dev/null || true
```

## Upgrade Package

```bash
python3 -m pip install --upgrade metaclaw
metaclaw upgrade --migrations-only
```

`metaclaw upgrade` auto-detects pending config migrations. Use `--migrations-only` for package installs so it does not run the source-tree update flow.

## Verify

```bash
metaclaw doctor
metaclaw status
```

If the service was already running, restart it:

```bash
metaclaw restart --no-logs
```
