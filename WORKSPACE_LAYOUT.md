# Workspace and Source Layout

This repository is the public MetaClaw source and installer distribution. Runtime data is intentionally kept out of Git.

## Public Source Area

These paths are versioned and safe to publish:

```text
README.md
INSTALL.md
RELEASE_CHECKLIST.md
scripts/install.sh
npm/bin/metaclaw-install.js
package.json
metaclaw/metaclaw   # Bundled Python MetaClaw source
metaclaw/metaclaw/skills  # Builtin skills shipped with the product
```

## Local Workspace Area

These paths are local runtime/user data and are ignored by Git:

```text
data/
knowledge/
memory/
skills/
reports/
logs/
tmp/
.claude/
metaclaw/config.json
metaclaw/data/
metaclaw/logs/
```

They may exist on your machine, but they are not part of the public release.

## User Install Layout

The installer creates the same separation on user machines:

```text
~/.metaclaw/src        # Git checkout / source code
~/.metaclaw/venv       # Python virtual environment
~/.metaclaw/workspace  # Runtime workspace and user data
~/.local/bin/metaclaw
~/.local/bin/metaclaw-update
```

## Skill Layout

MetaClaw follows the same separation model used by CowAgent:

- Builtin skills live in the source tree at `metaclaw/metaclaw/skills/`.
- User-installed or agent-created skills live in the runtime workspace at `skills/`.
- When both locations contain the same skill name, the workspace skill wins.
- Builtin skills are loaded from source; they are not copied into the source root or treated as personal workspace data.

## Rule

Do not commit runtime data, credentials, logs, local memory databases, screenshots, generated reports, or personal knowledge files.

If a file is reusable product documentation, put it in `docs/`.
If a file is a builtin product skill, put it in `metaclaw/metaclaw/skills/`.
If a file is a personal/custom skill, keep it under the local workspace.
If a file is personal/runtime state, keep it under the local workspace paths above.
