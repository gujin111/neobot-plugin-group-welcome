# Changelog

## 1.1.0 — 2026-11-12

适配官方机器人通道的 13 位合成 ID（真实群号/QQ 号与官方 openid 无法互转，只能人工绑定）。

- `groups[].group_id` 写真实群号或写合成 ID 都能命中：通过宿主 `neobot_app.user_identity`
  的 `group_number_for` 反查后再比对
- 新增模板变量 `{raw_id}` / `{raw_group_id}`：展示用 `{id}` / `{group_id}` 优先显示绑定后的
  真实号码，原始通道 ID 单独保留
- `/欢迎 状态` 增加身份信息：通道 ID、是否已绑定真实群号、未绑定时提示 `/linkgroup`
- `{at}` 仍用通道原始 ID 发送（官方协议只认 openid）
- 没有 `user_identity` 模块（纯 OneBot）时行为与 1.0.0 完全一致
- 已知限制写进 README：官方通道不推送群成员变动事件、也没有成员列表接口，纯官方模式下
  本插件不会被触发，需要 `adapter.mode = dual` 让 OneBot 侧提供入群事件

## 1.0.0 — 2026-11-12

首个版本。

- 入群欢迎：监听 OneBot `notice/group_increase`，模板支持 `{at}` `{name}` `{id}` `{group}` `{group_id}` `{time}` `{date}` `{br}` 等变量，`{at}` 生成真正的 at 消息段
- 合并进群：`delay_seconds > 0` 时滑动窗口合并，累计 12 人立即发送
- 按群定制：`[[groups]]` 每群独立模板 / 独立开关，未配置的群回落全局
- 退群提示：监听 `notice/group_decrease`，默认关闭，`kick_me` 与机器人自身事件自动跳过
- 命令：`/欢迎 预览`（按实时配置发一条示例）、`/欢迎 状态`（查看本群生效配置）
- 离线自测：`devtools/smoke_test.py`，38 项断言，不依赖 NeoBot / pydantic
