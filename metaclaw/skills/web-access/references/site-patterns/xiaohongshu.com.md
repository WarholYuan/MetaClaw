---
domain: xiaohongshu.com
aliases: [小红书, RED]
updated: 2026-04-27
---

## 平台特征

- 反爬策略严格，静态请求缺少 xsec_token 会被拦截
- 内容以图文笔记为主，视频内容也很常见
- 创作者平台需要登录后操作
- 搜索结果页面动态加载，需滚动激活

## 有效模式

- 搜索结果页：`https://www.xiaohongshu.com/search_result?keyword=xxx`
- 笔记详情页：`https://www.xiaohongshu.com/explore/NOTE_ID`
- 个人主页：`https://www.xiaohongshu.com/user/profile/USER_ID`
- 使用 browser evaluate 获取图片 URL 后用 vision 分析

## 已知陷阱

- URL 中缺失 xsec_token 会导致 403 或重定向到登录页
- 静态抓取无效，必须用 browser 访问
- 频繁操作可能触发验证码
