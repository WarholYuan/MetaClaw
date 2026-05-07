# Install MetaClaw

MetaClaw is a new personal AI agent project with a Python application core and a release workflow designed for simple local installation. Users can install it with either `curl` or `npm`.

## curl

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash
```

Custom repo, branch, and install paths:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash -s -- \
  --repo https://github.com/WarholYuan/MetaClaw.git \
  --branch main \
  --dir "$HOME/.metaclaw/src" \
  --workspace "$HOME/.metaclaw/workspace"
```

Install browser support too:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash -s -- --browser
```

## Optional OpenCLI Browser Automation

MetaClaw can use OpenCLI as an optional Agent tool for browser automation through the user's existing Chrome session. It is not required for installation.

Install and verify OpenCLI separately:

```bash
npm install -g @jackwener/opencli
opencli doctor
```

`opencli doctor` should report that the daemon, Browser Bridge extension, and connectivity checks are OK. When OpenCLI is not available, MetaClaw simply skips the `opencli` Agent tool and continues with the rest of the toolset.

## npm

From npm after publishing:

```bash
npx @mianhuatang913/metaclaw
```

From GitHub before npm publishing:

```bash
npx github:WarholYuan/MetaClaw
```

Pass installer options after `--`:

```bash
npx @mianhuatang913/metaclaw -- --branch main --browser
```

## Updates

Users can update by running either installer command again:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash
```

or:

```bash
npx @mianhuatang913/metaclaw
```

The installer also creates a local update command:

```bash
metaclaw-update
```

`metaclaw-update` reuses the saved install settings from `~/.metaclaw/install.env`, pulls the latest MetaClaw source, and reinstalls the Python package into the existing virtual environment.

## After Installation

```bash
metaclaw help
metaclaw start
```

The installer keeps source code and runtime data separate:

```text
~/.metaclaw/src        # Git checkout / source code
~/.metaclaw/venv       # Python virtual environment
~/.metaclaw/workspace  # Agent workspace, config, and runtime data
~/.local/bin/metaclaw  # CLI shim
```

If `metaclaw` is not found after installation, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## What the Installer Does

1. Clones or updates the GitHub repo.
2. Verifies the bundled Python application source.
3. Creates or reuses the Python virtual environment.
4. Installs MetaClaw with `pip install -e`.
5. Creates `metaclaw` and `metaclaw-update` shims in `~/.local/bin`.
6. Writes `config.json` into the workspace and keeps runtime data outside the source checkout.

## Publisher Checklist

Before publishing, replace `WarholYuan/MetaClaw` in these files if your GitHub repo path is different:

- `scripts/install.sh`
- `INSTALL.md`
- `package.json`

Publish npm package:

```bash
npm publish --access public
```

GitHub Release assets are uploaded separately from source control. Use the macOS one-click files from `dist/` as release attachments, and do not commit `dist/` into Git.
