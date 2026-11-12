# Changelog

## 1.0.0 — 2026-11-12

首个版本。

- 入群欢迎：监听 OneBot `notice/group_increase`，模板支持 `{at}` `{name}` `{id}` `{group}` `{group_id}` `{time}` `{date}` `{br}` 等变量，`{at}` 生成真正的 at 消息段
- 合并进群：`delay_seconds > 0` 时滑动窗口合并，累计 12 人立即发送
- 按群定制：`[[groups]]` 每群独立模板 / 独立开关，未配置的群回落全局
- 退群提示：监听 `notice/group_decrease`，默认关闭，`kick_me` 与机器人自身事件自动跳过
- 命令：`/欢迎 预览`（按实时配置发一条示例）、`/欢迎 状态`（查看本群生效配置）
- 离线自测：`devtools/smoke_test.py`，38 项断言，不依赖 NeoBot / pydantic
