# group_welcome — NeoBot 入群欢迎插件

给 [NeoBot](https://github.com/SuperQuail/NeoBot) 用的入群欢迎 / 退群提示插件，走 NeoBot 自己的插件 API（`neobot_modloader`），**不是 Koishi 插件**，装到 Koishi 里没有任何效果。

功能：

- 有人进群自动欢迎，消息里可以真正 @ 到新成员（不是纯文本的 `@123456`）
- 模板里能用昵称、QQ 号、群名、时间等变量，`{at}` 可以放在句子的任意位置
- **合并进群**：几秒内连续进人（拉群、爆群）只发一条消息，不会刷屏
- **按群定制**：不同群不同文案，也可以单独关掉某个群
- 可选退群提示（默认关闭）
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
| `groups` | list | `[]` | 按群定制，每个群一条 |

### 模板变量

| 变量 | 含义 | 合并时的行为 |
| --- | --- | --- |
| `{at}` | @ 新成员 | 每个人都 @ 一次 |
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
| `/欢迎 状态` | 打印本群生效的模板、开关、合并窗口 |
| `/欢迎` / `/欢迎 帮助` | 变量速查 |
| `/welcome`、`/入群欢迎` | 同一命令的别名 |

命令注册在宿主命令表里（权限 0 = 所有人），因此 `/help` 里能看到，并带 `[来源: group_welcome]` 标记。

## 官方机器人通道（13 位合成 ID）

NeoBot 2.1.0a8 起，新部署默认走 QQ 官方机器人通道（`adapter.mode = official`）。官方只给 openid，NeoBot 换成 13 位合成号（群 `9.5T…`、用户 `9.0T…`），和真实群号/QQ 号**没有任何 API 能互转**，只能人工绑定。

本插件对这件事的处理：

1. **配置照旧写真实群号**。`groups[].group_id = 123456789` 在官方通道下也能命中：插件通过宿主的 `neobot_app.user_identity` 把进来的合成群号反查成真实群号再比对，写合成 ID 也能匹配。
2. **展示自动用真实号**。`{group_id}`、`{id}`、`/欢迎 状态` 都优先显示绑定后的真实号，没绑定才显示合成号；想拿原始 ID 用 `{raw_group_id}` / `{raw_id}`。
3. **`{at}` 始终用合成 ID 发**——官方协议只认 openid，这是对的，别改成真实号。

绑定方法（宿主内置，一次一个群）：

```text
/linkgroup 123456789        # 在目标群里由管理员发，把当前群绑定成这个真实群号
/linkqq @某人 10001         # 同理，绑定成员的 QQ 号
```

映射存在 `data/user_qq_map.json`，绑定后 `/欢迎 状态` 会显示「已绑定真实群号 xxx」。

> ⚠️ **必须先知道的一件事**：官方通道**不推送群成员变动事件**。
> `packages/adapter/src/neobot_adapter/official/events.py` 里 `MESSAGE_EVENTS` 只有
> `C2C_MESSAGE_CREATE` / `GROUP_AT_MESSAGE_CREATE` / `GROUP_MESSAGE_CREATE` 三种消息事件，
> 其它 dispatch 一律丢弃；同时 `get_group_member_list` 在官方通道直接返回 `[]`（没有成员列表接口）。
> 所以**纯官方通道下本插件不会被触发**——不是 ID 对不上，是根本没有「有人进群」这个信号。
> 想要真正的入群欢迎，让 NeoBot 跑 `adapter.mode = dual`（同时挂 OneBot/NapCat），
> 入群事件由 OneBot 侧带来，群号天然就是真实群号，本插件直接可用。

## 排错

| 现象 | 排查方向 |
| --- | --- |
| 进群完全没反应 | ① 面板里 `group_welcome` 是否已启用；② 协议端是否在推 `group_increase`（NapCat 的日志里能看到 `notice` 事件）；③ `enabled`、该群 `enabled`、`template` 是否被关/清空 |
| 官方通道下收不到欢迎 | 正常现象：官方通道没有群成员变动事件（见上一节），改 `adapter.mode = dual` 用 OneBot 侧触发 |
| 有欢迎语但没 @ 到人 | 模板里少了 `{at}`；部分协议端对群成员变动事件不带昵称，`{at}` 仍然可用 |
| `{name}` 显示成 QQ 号 | 群成员资料接口没返回（比如人刚进群、缓存未命中），属正常回退 |
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
