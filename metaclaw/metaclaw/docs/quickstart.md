# MetaClaw Quickstart

## 1. Install

```bash
pip install metaclaw
```

## 2. Initialize

```bash
metaclaw init
```

## 3. Configure DeepSeek

Open `~/.metaclaw/.env` and add your DeepSeek key:

```bash
DEEPSEEK_API_KEY=your_deepseek_api_key
```

DeepSeek is the default provider when `model_provider` is not set.

## 4. Configure Feishu Channel

Add Feishu credentials through your config or environment:

```bash
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
```

Set the channel to Feishu in `config.json`:

```json
{
  "channel_type": "feishu",
  "model_provider": "deepseek"
}
```

## 5. Run

```bash
metaclaw run
```

Check status and logs:

```bash
metaclaw status
metaclaw logs
```
