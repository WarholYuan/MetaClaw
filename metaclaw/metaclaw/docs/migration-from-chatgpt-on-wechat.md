# Migrating From The Upstream Project

This guide is for users who previously ran the upstream WeChat bot project and want to move to MetaClaw.

## What Changes

- Runtime data moves to `~/.metaclaw/`.
- Agent workspace defaults to `~/.metaclaw/workspace`.
- Provider setup is China-first: DeepSeek, Doubao, and Moonshot are first-class options alongside OpenAI-compatible endpoints.
- The CLI command is `metaclaw`.

## Before You Start

Back up your old deployment directory and config:

```bash
cp -a config.json config.json.before-metaclaw
cp -a ~/.metaclaw ~/.metaclaw.before-upgrade 2>/dev/null || true
```

## Install MetaClaw

```bash
python3 -m pip install metaclaw
metaclaw init
```

## Move Config

Copy your existing `config.json` to:

```bash
~/.metaclaw/config.json
```

Run the migration framework:

```bash
metaclaw upgrade --migrations-only
```

The first migration renames legacy brand keys and rewrites old runtime paths to MetaClaw defaults where it can do so safely.

## Review Provider Settings

For a China deployment, choose one primary provider:

```json
{
  "model_provider": "deepseek",
  "model": "deepseek-chat"
}
```

Then add the provider key to `~/.metaclaw/.env`.

## Verify

```bash
metaclaw start
metaclaw status
```
