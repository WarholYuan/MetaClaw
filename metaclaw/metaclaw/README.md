# MetaClaw

MetaClaw - Multi-Platform AI Agent

## Install

```bash
pip install metaclaw
```

## Initialize

```bash
metaclaw init
```

This creates `~/.metaclaw/.env` with provider API key placeholders:

```bash
DEEPSEEK_API_KEY=
DOUBAO_API_KEY=
MOONSHOT_API_KEY=
OPENAI_API_KEY=
```

## Configure Provider

DeepSeek, Doubao, and Moonshot are recommended providers for users in China. Add one API key to `~/.metaclaw/.env`, for example:

```bash
DEEPSEEK_API_KEY=your_api_key_here
```

MetaClaw defaults to the DeepSeek provider when no provider is configured.

## Run

```bash
metaclaw run
```

`metaclaw run` is an alias for the existing service start path. You can also use:

```bash
metaclaw start
metaclaw status
metaclaw logs
metaclaw doctor status
metaclaw upgrade
metaclaw version
```

## Feishu

Set the Feishu channel credentials in your config or environment, then run MetaClaw:

```bash
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
metaclaw run
```

See [docs/quickstart.md](docs/quickstart.md) for a step-by-step Feishu quickstart.
