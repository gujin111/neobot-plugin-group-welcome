# Changelog

## 1.8.0 — 2026-11-13

修官方通道两个观感问题：欢迎语没有 @、退群显示一串 openid。

- **官方通道的 @ 改走 Markdown**：官方纯文本消息（`msg_type=0`）发不出真正的 @，
  适配器会直接丢弃 `at` 段（`official/send.py`）。现在检测到 ID 是 openid 字符串且
  模板含 `{at}` 时，发 `official_markdown` 段，内容里用 `<qqbot-at-user id="openid" />`；
  发送失败自动回退纯文本（不报错、不刷屏）
- **昵称缓存**：新增 `_names`（持久化在 `seen.json` 的 `names` 字段），
  从群消息的 `sender.nickname/card`、入群事件、成员资料接口三处收集；
  退群事件只有 openid（人已退群、接口查不到）时用它补 `{name}`
- 事件订阅新增 `post_type="message"`（只记昵称，不回复、不拦截）

## 1.7.0 — 2026-11-13

适配 NeoBot **2.1.0a9**（官方通道改为直出 openid 字符串 + 原生成员事件）。

- `_as_id()` 全面替代事件/轮询/命令里的 `_to_int()`：官方通道的 `455C4F9F…` 这类 openid
  原样保留，不再被当成非法 ID 丢掉（此前 openid 入群事件会被静默忽略）
- 官方 2.1.0a9 起适配器把成员增减映射成 `group_increase` / `group_decrease`，
  本插件直接消费，`{at}` 用 openid 发
- 机器人自身判断改为字符串比较，`self_id` 是 openid 时也能正确跳过
- 轮询目标排序改为 `key=str`，兼容 int / openid 混排；成员列表里的 openid 同样走 `_as_id`
- README 重写官方通道一节：a8（合成号）与 a9（openid）、事件来源、成员列表能力边界

## 1.6.0 — 2026-11-13

`/欢迎` 的帮助页改成 HTML 卡片（图片）。

- 用宿主 `neobot_app.runtime.html_card` 渲染：标题 + 命令表 + 模板变量表 + 状态备注
- 发送优先走 `CommandContext.service.send_image_bytes`（与宿主 `/help` 同一条路，
  官方通道也走这个），失败退回 `Reply.image`，再失败回退纯文本
- 新增配置 `help_image_enabled` / `help_image_theme` / `help_image_width`

## 1.5.1 — 2026-11-13

修官方通道 `/欢迎` 误报「这个命令只能在群里用」。

- 根因：命令里只认 `event["group_id"]` 并强制 `int()`；官方通道的会话 ID 是
  `455C4F9F…` 这类 openid，转换失败就被当成「不在群里」
- `welcome_command` 改为优先取宿主 `CommandContext.conv_id`（宿主自己回复也用它，
  一定是可发送的会话 ID），再按 `group_id` / `group_openid` / `chat_id` /
  `conversation_id` 依次兜底
- 新增 `_as_id`：纯数字转 int，openid 这类字符串原样保留；`groups[].group_id`
  现在也接受 openid，匹配时按字符串比较
- 确实拿不到会话 ID 时，日志会打出 event keys / conv_id / kind，方便定位

## 1.5.0 — 2026-11-12

把「官方通道欢迎」从「首句发言近似」改成**自己检测入群**：

- 新增轮询检测：`join_poll_enabled` 打开后，按 `join_poll_seconds` 定时调
  `get_group_member_list`，与本地名册做差集，多出来的人按入群处理
  - 首轮只登记名册，不补欢迎；新人当场入册，不会重复
  - 与真实 `group_increase` 共用同一个欢迎出口（模板 / `{at}` / 合并窗口 / 按群定制）
  - 名册落盘 `plugins_data/group_welcome/seen.json`，`/欢迎 重置` 可清空
  - 拉不到名单（官方通道固定返回 `[]`）时安静跳过，不刷日志
- 删除「首句发言合成 notice」那条路径：`first_speak_enabled` / `first_speak_warmup_minutes`
  以及消息事件订阅一并移除
- `/欢迎 状态` 改为显示轮询开关、间隔与本群已记录人数

## 1.4.0 — 2026-11-12

- 官方通道的入群事件改为**由插件合成**：首句检测到新面孔后构造
  `post_type=notice / notice_type=group_increase / sub_type=first_speak`，
  再交给与真实 `group_increase` 完全相同的处理函数，模板、合并窗口、按群定制全部复用
  - 删除 `first_speak_template`（不再有独立的欢迎语，统一用 `template`）
- 删除 `/指令图`：宿主 `/help` 本身就是图片卡片（分页、权限维度、预渲染缓存），
  插件命令会自动出现在里面，不需要第二个命令
  - 一并移除 `command_image_enabled` / `command_image_theme` / `command_image_width`

## 1.3.0 — 2026-11-12

新增 `/指令图`：把指令总览以图片发到 QQ。

- 从宿主 `command_service` 取命令表，按调用者权限过滤，再交给
  `neobot_app.runtime.html_card` 渲染成 PNG
- 三级回退：卡片渲染不可用 → 文字版；图片发送失败 → 文字版；关键词无命中 → 提示
- 关键词按命令名/用法/说明/来源做子串过滤，例如 `/指令图 欢迎`
- 新增配置 `command_image_enabled` / `command_image_theme` / `command_image_width`
- 别名 `/helpimg`、`/命令图`、`/指令总览`

## 1.2.0 — 2026-11-12

官方通道没有入群事件，补一条能落地的替代路径。

- 新增「首句欢迎」：`first_speak_enabled` 打开后，按「没见过的发言人」触发欢迎，
  用于官方机器人通道（拿不到 `group_increase`、也拿不到成员列表）
  - 第一次见到某个群时只建档并记录当前发言人，避免把全群老人挨个欢迎
  - `first_speak_warmup_minutes` 启蒙期内只记录、不欢迎
  - 入群时已欢迎过的人会写进同一份名单，不会二次欢迎
  - 名单落盘 `plugins_data/group_welcome/seen.json`，`/欢迎 重置` 可清空本群
  - 默认关闭，对 OneBot 通道零影响
- `/欢迎 状态` 增加「首句欢迎」状态与「本群 notice 事件」计数（官方通道恒为 0，
  可直接用来验证当前通道到底有没有推送成员变动）

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
