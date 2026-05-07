# Provider Configuration

MetaClaw can route model calls through China-friendly providers and OpenAI-compatible endpoints.

## DeepSeek

- Environment key: `DEEPSEEK_API_KEY`
- API base: `https://api.deepseek.com/v1`
- Common models: `deepseek-chat`, `deepseek-reasoner`
- Good default for China deployments because the official endpoint is accessible from mainland networks.

Example:

```json
{
  "model_provider": "deepseek",
  "model": "deepseek-chat",
  "deepseek_api_key": "",
  "deepseek_api_base": "https://api.deepseek.com/v1"
}
```

## Doubao

- Environment keys: `DOUBAO_API_KEY` or `ARK_API_KEY`
- API base: `https://ark.cn-beijing.volces.com/api/v3`
- Configure model names to match the endpoint deployed in Volcengine Ark.

Example:

```json
{
  "model_provider": "doubao",
  "model": "doubao-pro-32k",
  "ark_api_key": "",
  "ark_base_url": "https://ark.cn-beijing.volces.com/api/v3"
}
```

## Moonshot

- Environment key: `MOONSHOT_API_KEY`
- API base: `https://api.moonshot.cn/v1`
- Common models: `moonshot-v1-8k`, `moonshot-v1-32k`, `moonshot-v1-128k`

Example:

```json
{
  "model_provider": "moonshot",
  "model": "moonshot-v1-8k",
  "moonshot_api_key": "",
  "moonshot_base_url": "https://api.moonshot.cn/v1"
}
```

## OpenAI

- Environment key: `OPENAI_API_KEY`
- API base: `https://api.openai.com/v1`
- Mainland China deployments usually need a compliant proxy, private network egress, or an OpenAI-compatible gateway.

Example:

```json
{
  "model_provider": "openai",
  "model": "gpt-4o-mini",
  "open_ai_api_key": "",
  "open_ai_api_base": "https://api.openai.com/v1",
  "proxy": ""
}
```

## Priority

Runtime environment variables override values in `config.json`. Keep secrets in `~/.metaclaw/.env` when possible.
