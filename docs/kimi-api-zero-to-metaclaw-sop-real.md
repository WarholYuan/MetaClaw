# Kimi API 从 0 到 MetaClaw 配置 SOP

> 面向对象：第一次使用 Kimi API 的新人。
> 目标：完成 Kimi API 账号准备、充值、API Key 获取、余额与消耗查看、发票申请，并把 Key 配到 MetaClaw。
> 平台：国内版 Kimi API 开放平台。

## 1. 先分清楚：Kimi 网页会员不是 API 余额

开始前先确认一件事：在 Kimi 网页端聊天使用的会员权益，和 Kimi API 控制台里的 API 余额不是同一套体系。MetaClaw 调用模型时消耗的是 API 账户余额。

常用入口：

- Kimi API 文档：<https://platform.kimi.com/docs>
- Kimi API 控制台：<https://platform.moonshot.cn/console>
- API Key 管理：<https://platform.moonshot.cn/console/api-keys>
- 国内版 API Base：`https://api.moonshot.cn/v1`

【图 1：Kimi API 文档首页】


## 2. 注册、登录与实名认证

1. 打开 Kimi API 控制台：<https://platform.moonshot.cn/console>。
2. 选择微信、手机号或账号密码登录。
3. 首次使用时，按页面提示完成个人实名认证或企业认证。
4. 如果是公司项目，优先使用企业认证账号，方便后续对公、发票和权限管理。

【图 2：Kimi 控制台登录入口】


【图 3：登录后控制台首页与实名认证入口，需登录账号后替换】


验收标准：

- 可以进入 Kimi API 控制台。
- 账号认证状态已完成，或页面不再拦截充值和创建 API Key。
- 已确认使用的是公司指定账号，而不是个人随手注册的临时账号。

## 3. 充值

1. 在控制台中进入「充值」「费用中心」「账单」或类似入口。
2. 选择充值金额。
3. 个人账号通常可以使用微信或支付宝扫码支付。
4. 企业账号按页面支持方式选择在线充值或对公汇款。
5. 支付完成后回到控制台，确认 API 余额增加。

【图 4：Kimi API 充值协议】


【图 5：充值、余额、消耗、发票后台页，需登录账号后替换】


注意事项：

- API 调用按量计费，余额不足会导致调用失败。
- 对公汇款到账可能不是实时的，以控制台余额为准。
- 培训新人时建议使用测试账号或小额充值。

## 4. 创建并保存 API Key

1. 打开 API Key 管理页：<https://platform.moonshot.cn/console/api-keys>。
2. 点击「创建 API Key」。
3. 填写清晰的 Key 名称，例如 `metaclaw-dev-姓名`、`metaclaw-test`、`metaclaw-prod`。
4. 创建后立即复制并保存到公司指定的密钥管理位置。
5. 不要关闭弹窗后才想起来保存，部分平台只展示一次完整 Key。

【图 6：API Key 管理入口】


安全要求：

- 不要把完整 API Key 发到飞书群、聊天窗口或截图里。
- 不要把 API Key 写进 Git 仓库。
- 如果 Key 泄露，立即删除旧 Key 并创建新 Key。
- 生产环境和测试环境分开使用不同 Key。

## 5. 查看余额和消耗

1. 在控制台进入「费用中心」「账单」「费用明细」或类似页面。
2. 查看当前 API 账户余额。
3. 查看按日期、模型或项目维度的消耗。
4. 如果发现异常消耗，先停用可疑 Key，再排查调用来源。

【图 7：Kimi API 余额与消耗帮助】


【图 8：Kimi API 价格常见问题】


说明：

- 官方帮助说明中，余额与消耗数据可能存在更新延迟。
- 日消耗和模型消耗适合用来排查成本异常。
- 如果 MetaClaw 报余额不足，先到这里确认 API 余额。

## 6. 申请发票

1. 在控制台进入「发票管理」或「费用中心」里的发票入口。
2. 选择可开票金额。
3. 填写发票抬头、税号、邮箱、地址电话等信息。
4. 提交后等待平台审核和开具。
5. 下载电子发票并交给财务归档。

注意事项：

- 个人认证账号通常只能按个人身份申请发票。
- 企业认证账号更适合公司报销、对公开票和财务归档。
- 发票规则以控制台页面和官方协议为准。

## 7. 在 MetaClaw 里配置 Kimi API Key

MetaClaw 已支持 Moonshot/Kimi。推荐使用环境变量配置，这样不会把密钥写进仓库。

### 推荐方式：环境变量

在运行 MetaClaw 的机器或部署平台里配置：

```bash
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxx
```

【图 9：MetaClaw 环境变量配置】


保存后重启 MetaClaw。

### 备选方式：config.json

如果当前部署使用 `config.json`，可以写：

```json
{
  "model": "kimi-k2.6",
  "moonshot_api_key": "sk-xxxxxxxxxxxxxxxx",
  "moonshot_base_url": "https://api.moonshot.cn/v1"
}
```

【图 10：MetaClaw config.json 配置】


说明：

- `model` 推荐先用 `kimi-k2.6`。
- `moonshot_api_key` 填 Kimi 控制台创建的 API Key。
- `moonshot_base_url` 使用国内版地址：`https://api.moonshot.cn/v1`。
- 如果环境变量和 `config.json` 同时存在，MetaClaw 会优先使用环境变量里的 `MOONSHOT_API_KEY`。

### 可选方式：OpenAI 兼容配置

只有在项目已经统一走 OpenAI 兼容配置时使用：

```json
{
  "bot_type": "openai",
  "model": "kimi-k2.6",
  "open_ai_api_base": "https://api.moonshot.cn/v1",
  "open_ai_api_key": "sk-xxxxxxxxxxxxxxxx"
}
```

## 8. 重启并验证

1. 保存配置后重启 MetaClaw。
2. 在 MetaClaw 对话入口发送：`你好，请用一句话介绍你自己。`
3. 能正常回复，说明 Key、模型和余额基本可用。

常见问题：

| 现象 | 常见原因 | 处理方式 |
| --- | --- | --- |
| 鉴权失败 | Key 填错、复制多了空格、Key 已删除 | 重新复制 Key，必要时重建 |
| 余额不足 | API 账户未充值或余额用完 | 回控制台充值 |
| 模型不存在 | `model` 写错或账号无权限 | 先用 `kimi-k2.6` 验证 |
| 配置没生效 | 改完没重启，或改错机器 | 重启 MetaClaw，确认运行环境 |
| 国内/国际混用 | Key 和 API Base 不属于同一平台 | 国内版使用 `https://api.moonshot.cn/v1` |

## 9. 发布前检查

- 所有真实截图都已打码。
- 文档里没有完整 API Key。
- `MOONSHOT_API_KEY`、`moonshot_api_key`、`moonshot_base_url` 拼写正确。
- 国内版 API Base 是 `https://api.moonshot.cn/v1`。
- 充值、发票、余额截图来自公司允许展示的账号。

## 10. 官方参考

- Kimi API 文档：<https://platform.kimi.com/docs>
- Kimi API 主要概念：<https://platform.kimi.com/docs/introduction>
- Kimi API 充值协议：<https://platform.kimi.com/docs/agreement/payment>
- Kimi API 价格常见问题：<https://platform.kimi.com/docs/pricing/faq>
- Kimi API 余额与消耗说明：<https://www.kimi.com/help/kimi-api/api-balance-and-usage>
- MetaClaw Kimi 配置：`metaclaw/metaclaw/docs/models/kimi.mdx`
