# MetaClaw Installation

This guide is optimized for users in China who install MetaClaw from PyPI and use DeepSeek, Doubao, Moonshot, or OpenAI-compatible providers.

## Requirements

- Python 3.10 or newer.
- A network path to PyPI. If downloads are slow, configure a local mirror:

```bash
python3 -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/master/scripts/install.sh | bash
```

Or install manually:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install metaclaw
metaclaw init
```

`metaclaw init` creates `~/.metaclaw/.env` when it does not exist.

## Provider Setup

Edit `~/.metaclaw/.env` and add at least one provider key.

### DeepSeek

```bash
DEEPSEEK_API_KEY=sk-...
```

Recommended config values:

```json
{
  "model_provider": "deepseek",
  "model": "deepseek-chat",
  "deepseek_api_base": "https://api.deepseek.com/v1"
}
```

### Doubao

Doubao uses Volcengine Ark credentials.

```bash
DOUBAO_API_KEY=...
ARK_API_KEY=...
```

Recommended config values:

```json
{
  "model_provider": "doubao",
  "model": "doubao-pro-32k",
  "ark_base_url": "https://ark.cn-beijing.volces.com/api/v3"
}
```

### Moonshot

```bash
MOONSHOT_API_KEY=sk-...
```

Recommended config values:

```json
{
  "model_provider": "moonshot",
  "model": "moonshot-v1-8k",
  "moonshot_base_url": "https://api.moonshot.cn/v1"
}
```

### OpenAI

OpenAI may require a proxy or a compatible gateway in mainland China.

```bash
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1
```

Recommended config values:

```json
{
  "model_provider": "openai",
  "model": "gpt-4o-mini",
  "open_ai_api_base": "https://api.openai.com/v1"
}
```

## Verify

```bash
metaclaw status
```

Start the service:

```bash
metaclaw start
```
