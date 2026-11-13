# group_welcome — NeoBot 入群欢迎插件

给 [NeoBot](https://github.com/SuperQuail/NeoBot) 用的入群欢迎 / 退群提示插件，走 NeoBot 自己的插件 API（`neobot_modloader`），**不是 Koishi 插件**，装到 Koishi 里没有任何效果。

功能：

- 有人进群自动欢迎，消息里可以真正 @ 到新成员（不是纯文本的 `@123456`）
- 模板里能用昵称、QQ 号、群名、时间等变量，`{at}` 可以放在句子的任意位置
- **合并进群**：几秒内连续进人（拉群、爆群）只发一条消息，不会刷屏
- **按群定制**：不同群不同文案，也可以单独关掉某个群
- 可选退群提示（默认关闭）
- 通道不推入群事件时（官方机器人），插件可以**定时拉群成员列表做差集**，自己检测谁是新来的（默认关闭，见下文）
- 指令总览不再额外加命令：宿主 `/help` 本身就是图片卡片，装好后会自动带上本插件的命令与 `[来源: group_welcome]` 标记
- 命令：`/欢迎 预览` 在当前群发一条示例、`/欢迎 状态` 查看本群生效配置

## 环境要求

| 项 | 要求 |
| --- | --- |
| NeoBot | 带 `neobot-modloader` 的版本（`neobot-app`，Python 3.13+） |
| 协议端 | OneBot 实现需要上报 `notice/group_increase`（NapCat 默认上报） |
| 其他依赖 | 无。不用数据库、不装第三方包 |

## 安装

1. 把整个目录复制到 NeoBot 的插件目录，**目录名改成 `group_welcome`**（与插件名一致最稳妥）：

   ```bash
   cp -r neobot-plugin-group-welcome <NeoBot 数据目录>/plugins/group_welcome
   ```

   插件目录默认是 `./plugins`（宿主 `config.toml` 的 `[plugins] dir`），网页面板「插件」页能看到实际路径。

2. 重启 NeoBot，或在网页面板「插件管理」里刷新/加载。列表里出现 `group_welcome` 即成功。
3. 进群试一下：随便拉个小号进群，群里有 @ 和欢迎语就通了。

> 改完代码想直接看效果：宿主 `config.toml` 里设 `[plugins] watch = true`，本插件声明了 `hot_reload = true`，保存 `.py` 会自动重载。

## 配置

两种改法等价，推荐第一种：

- 网页面板 →「插件」→ `group_welcome` →「配置」，按表单改，保存后点「重载」生效（不用重启进程）；
- 直接编辑 `data/plugins_data/group_welcome/config.toml`（**扁平 TOML，没有 `[config]` 外壳**），保存后同样重载一次。

`plugin.toml` 里的 `[config]` 只是打包默认值，升级插件会覆盖它；你自己的配置在 `plugins_data/` 下，升级不丢。

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | bool | `true` | 总开关，关掉后所有群都不发欢迎 |
| `template` | str | `欢迎 {at} 加入本群，记得先看群公告～` | 欢迎语模板 |
| `delay_seconds` | float | `0` | 合并窗口（秒）。`0` = 逐条立即发；`>0` = 这段时间内进群的人合成一条 |
| `leave_enabled` | bool | `false` | 是否发退群提示 |
| `leave_template` | str | `{name} 离开了本群。` | 退群提示模板 |
| `join_poll_enabled` | bool | `false` | 自己检测入群：定时拉群成员列表做差集，不依赖通道推送 notice |
| `join_poll_seconds` | int | `300` | 轮询间隔（秒），小于 60 按 60 算 |
| `join_poll_groups` | list | `[]` | 要轮询的群；留空用 `groups` 里配置的群，再不行问适配器要群列表 |
| `help_image_enabled` | bool | `true` | `/欢迎` 的帮助页渲染成 HTML 卡片图片（失败自动回退文字） |
| `help_image_theme` | str | `default` | 帮助卡片主题（宿主内置主题名） |
| `help_image_width` | int | `760` | 帮助卡片宽度（像素） |
| `groups` | list | `[]` | 按群定制，每个群一条 |

### 模板变量

| 变量 | 含义 | 合并时的行为 |
| --- | --- | --- |
| `{at}` | @ 新成员（官方通道自动改用 Markdown 内嵌 @） | 每个人都 @ 一次 |
| `{name}` / `{user}` / `{nickname}` | 群名片 → 昵称 → QQ 号 | 用 `、` 连起来 |
| `{id}` / `{user_id}` | QQ 号（官方通道显示绑定后的真实号，未绑定则显示合成 ID） | 用 `、` 连起来 |
| `{raw_id}` | 通道原始用户 ID（官方通道是 13 位合成号） | 用 `、` 连起来 |
| `{group}` / `{group_name}` | 群名（查不到就用群号） | 同上 |
| `{group_id}` | 群号（官方通道显示绑定后的真实群号） | — |
| `{raw_group_id}` | 通道原始群 ID（官方通道是 13 位合成号） | — |
| `{time}` | `2026-11-12 14:30:00` | 发送时刻 |
| `{date}` | `2026-11-12` | 发送时刻 |
| `{clock}` | `14:30:00` | 发送时刻 |
| `{bot}` | 机器人自己的 QQ 号 | — |
| `{br}` | 换行 | — |

不认识的 `{xxx}` 会原样保留，方便你写「大括号」文案。

### 按群定制

在 `config.toml` 里追加（注意是 `[[groups]]`，可写多段）：

```toml
template = "欢迎 {at} 加入本群～"
delay_seconds = 5

[[groups]]
group_id = 123456789
template = "欢迎 {at} 加入【摸鱼办】！本群禁止发广告，先看置顶。"
leave_template = "{name} 走好，记得常回来看看。"

[[groups]]
group_id = 987654321
enabled = false        # 这个群不欢迎，也不发退群
```

规则很简单：

- `group_id` 命中就用该群的 `template` / `leave_template`，留空则回落到全局值；
- `enabled = false` 的群，欢迎和退群都不发；
- 没配的群一律用全局配置。

### 合并窗口怎么选

- `0`：来一个发一条。人少、想即时性强的时候用。
- `3` ~ `10`：推荐。拉群/爆群时把十几个人合成一条，附带十几个 @。
- 窗口是**滑动**的：窗口内每来一个人就重新计时，所以「分批进群」也会被并成一条；累计到 12 人立刻发，不会无限等下去。

## 命令

| 命令 | 作用 |
| --- | --- |
| `/欢迎 预览` | 在当前群按实时配置发一条示例（@ 你自己），用来对效果 |
| `/欢迎 状态` | 打印本群生效的模板、开关、合并窗口、身份绑定情况 |
| `/欢迎 重置` | 清空本群的成员名册，下一轮轮询重新登记（不补欢迎） |
| `/欢迎` / `/欢迎 帮助` | 帮助页：HTML 卡片（命令表 + 模板变量表） |
| `/welcome`、`/入群欢迎` | 同一命令的别名 |

命令注册在宿主命令表里（权限 0 = 所有人），因此 `/help` 里能看到，并带 `[来源: group_welcome]` 标记。

> 指令总览**不另外造命令**：宿主的 `/help` 已经输出图片卡片（带分页、权限维度与预渲染缓存），装好本插件后它会自动多出 `/欢迎` 这一条。
>
> 本插件自己的帮助页 `/欢迎` 同样出图：用 `render_card_html` 生成「命令 + 模板变量」两张表，
> 发送优先走 `CommandContext.service.send_image_bytes`（与宿主 `/help` 同一条链路，官方通道也能发），
> 失败退 `Reply.image`，再失败回退纯文本。Chromium 没起来时就一直是文字版，命令不会报错。

## 官方机器人通道（openid / 合成 ID）

官方适配器的 ID 形态随版本变过：

| 版本 | 事件里的群/用户 ID |
| --- | --- |
| 2.1.0a8 及更早 | 13 位合成号（群 `9.5T…`、用户 `9.0T…`），由 `IdentityMap` 从 openid 生成 |
| **2.1.0a9+（当前最新）** | **直接是 openid 字符串**（`455C4F9F…`），`IdentityMap` 降级为只读迁移 |

本插件两种都认：

1. **ID 统一走 `_as_id()`**：纯数字转 `int`，其余（openid）原样保留字符串。事件、轮询、
   命令三条路径共用，不会再出现 `int("455C…")` 失败导致的静默丢弃。
2. **`groups[].group_id` 支持三种写法**：真实群号 `123456789`、13 位合成号、openid 字符串，
   匹配时按字符串比。
3. **`{at}` 用事件里的原始 ID 发送**（官方通道就是 openid）；`{id}` / `{group_id}` 能经
   `neobot_app.user_identity` 反查出真实号就显示真实号，否则显示原始 ID，
   想看原始值用 `{raw_id}` / `{raw_group_id}`。
4. **命令优先用宿主 `CommandContext.conv_id`**，再按 `group_id` / `group_openid` / `chat_id` /
   `conversation_id` 兜底——官方通道下 `conv_id` 就是 openid，宿主自己也是用它回复的。

想让它显示真实群号/QQ 号（可选，纯展示用）：

```text
/linkgroup 123456789        # 在目标群里由管理员发，把当前群绑定成这个真实群号
/linkqq @某人 10001         # 同理，绑定成员的 QQ 号
```

映射存在 `data/user_qq_map.json`，绑定后 `/欢迎 状态` 会显示「已绑定真实群号 xxx」。

> 2.1.0a9 新增了只读命令 `/get groupid` 与 `/get openid [@用户]`，可以直接把官方 ID 复制出来填配置，
> 不用再自己从日志里翻。

> 如果 `/欢迎` 仍然回「这个命令只能在群里用」，那是真的没拿到会话 ID：日志里会打一行
> `无法确定当前会话：event keys=[…] conv_id=… kind=…`，把那行发我，照着补映射即可。

### 入群事件从哪来

| 通道 / 版本 | 入群信号 | 本插件行为 |
| --- | --- | --- |
| OneBot（NapCat 等） | 适配器推 `group_increase` | 直接欢迎 |
| 官方 2.1.0a9+ | 适配器把官方成员增减事件映射成 `group_increase` / `group_decrease` | 直接欢迎（openid 字符串 ID） |
| 官方 2.1.0a8 及更早 | 只有消息事件，没有成员变动，成员列表也拿不到 | 无信号，需要轮询或升级 |

### 官方通道的 @ 与昵称

官方接口的纯文本消息（`msg_type=0`）**不支持真正的 @**，适配器会把 `at` 段直接丢掉——
`official/send.py` 里写得很直白：「纯文本消息发不出真正的 @；不制造假 @ 文本，需要 @ 请用 Markdown 卡片」。

本插件的处理：

- 检测到 ID 是 openid 字符串、且模板里有 `{at}` → 改发 `official_markdown` 段，内容形如
  `欢迎 <qqbot-at-user id="OPENID" /> 加入本群`；
- Markdown 被平台拒绝 → 自动回退纯文本（这条就没有 @ 了，但命令不报错，日志留一行 warning）。

昵称：官方 `group_decrease` 事件只给 openid，人又已经退群，接口也查不到名字。所以插件平时会把
群消息 `sender` 的昵称/名片记进 `seen.json` 的 `names`（入群事件和成员资料接口也会补），
退群时用缓存渲染 `{name}`。从没说过话、也没被记录过的成员只能显示原始 ID——这是平台数据缺失，
不是渲染问题。

### 自己检测入群（轮询成员列表，兜底）

不想依赖通道推送、或通道确实没有事件时，可以打开轮询：定时调 `get_group_member_list`，和上一轮的名册做差集。

```toml
join_poll_enabled = true
join_poll_seconds = 300        # 5 分钟一轮，最小 60
join_poll_groups = [123456789] # 留空则用 groups 里的群，再不行问适配器要群列表
```

工作方式：

- **首轮只登记**：第一次拿到某个群的名单时全部记进名册，不发欢迎——否则会把全群老人刷一遍；
- 之后每轮比对，`member_list − 名册 = 新人`，逐个走**和真实 `group_increase` 完全相同的欢迎逻辑**（模板、`{at}`、合并窗口、按群定制全部复用）；
- 新人当场写进名册，同一批不会重复欢迎；真实 notice 欢迎过的人也在名册里，两条路径天然去重；
- 名单存在 `plugins_data/group_welcome/seen.json`，`/欢迎 重置` 清空本群后下一轮重新登记。

**能力边界**：

| 通道 / 版本 | `get_group_member_list` | 轮询效果 |
| --- | --- | --- |
| OneBot（NapCat 等） | 正常返回 | 可用；不过它本来就推 `group_increase`，轮询只是兜底 |
| 官方 2.1.0a9+ | 走 `/v2/groups/{openid}/members`，返回 openid 成员 | 可用（ID 是 openid 字符串） |
| 官方 2.1.0a8 及更早 | 固定返回 `[]` | 拉不到名单，插件安静跳过 |

`/欢迎 状态` 里的「本群 notice 事件」一行可以直接验证当前通道有没有在推事件：官方 2.1.0a9+ 与 OneBot 都会累加。

## 排错

| 现象 | 排查方向 |
| --- | --- |
| 进群完全没反应 | ① 面板里 `group_welcome` 是否已启用；② 协议端是否在推 `group_increase`（NapCat 的日志里能看到 `notice` 事件）；③ `enabled`、该群 `enabled`、`template` 是否被关/清空 |
| 官方通道下收不到欢迎 | 先看版本：2.1.0a9+ 会推 `group_increase`，`/欢迎 状态` 的 notice 计数应该涨；a8 及更早没有事件，只能开 `join_poll_enabled`（那版也拿不到成员列表，需升级） |
| 有欢迎语但没 @ 到人 | 官方通道的纯文本消息发不出 @（适配器会丢弃 `at` 段），本插件会自动改发 Markdown 卡片；若仍是纯文本，说明 Markdown 被平台拒了，看日志里的「官方 Markdown 发送失败」。OneBot 通道检查模板里有没有 `{at}` |
| `{name}` 显示成 openid / QQ 号 | 取不到昵称时的回退。官方通道的退群事件只带 openid、人也已经退群，只能靠平时缓存的昵称；缓存里没有就显示原始 ID |
| 退群提示不出现 | 默认 `leave_enabled = false`；另外退群事件本身可能不带昵称 |
| 连续进人刷屏 | 把 `delay_seconds` 设成 3～10 |
| 群里出现「发送失败」日志 | 机器人被禁言/被踢/风控，插件只记 warning，不会影响其他功能 |
| 改了配置没生效 | 面板里点一次「重载」，或重启 NeoBot |

## 和 Koishi 版的区别

之前那份 Koishi 插件不能直接搬过来：NeoBot 是 Python 宿主，插件 API 是 `Plugin` + `ctx`（Koishi 是 JS + `Context` + `ctx.on`），OneBot 事件到插件手里是原始 `dict`，发送走 `ctx.send_group(group_id, MessageChain)`。所以这里是按 NeoBot 的 API 重写的，配置项和模板语法尽量沿用 Koishi 版的习惯（`{at}` / `{name}` / `{group}` 那一套）。

## 目录结构

```text
group_welcome/
├── __init__.py            # 插件本体（事件 / 渲染 / 合并 / 命令）
├── plugin.toml            # 清单与打包默认配置
├── README.md
└── devtools/smoke_test.py # 离线自测，不参与加载
```

`devtools/` 下没有 `__init__.py`，NeoBot 不会把它当插件加载。想跑自测（不需要装 NeoBot）：

```bash
python devtools/smoke_test.py
```

它会用最小 stub 跑通模板渲染、合并窗口、按群定制、开关与命令，输出 `ALL PASSED` 即通过。注意这只验证插件自身逻辑，真正的事件上报与发送仍要在真机上验收。

## License

MIT
