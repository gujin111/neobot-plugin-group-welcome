"""入群欢迎 / 退群提示 —— NeoBot 插件。

适配 https://github.com/SuperQuail/NeoBot 的插件 API（``neobot_modloader``）：
入口导出 ``plugin = Plugin(...)``，用 ``@plugin.event(post_type="notice", ...)``
订阅 OneBot 的群成员变动通知，用 ``ctx.send_group`` 主动发消息。

事件：OneBot ``notice/group_increase``（sub_type 为 approve / invite）与
``notice/group_decrease``（leave / kick / kick_me）。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from neobot_modloader import MessageChain, Plugin

#: 模板中的 {at} 先替换成这个哨兵，最后再拼成真正的 at 消息段
_AT_MARK = "\u0000at\u0000"

#: 只认 {identifier} 形态的占位符，不认识的保持原样
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: 合并窗口内累计到这么多人就直接发，不再等
_MAX_MERGE = 12

#: 合并窗口上限，防止把 delay_seconds 写成一个离谱的值
_MAX_DELAY = 600.0


class GroupRule(BaseModel):
    """单个群的定制项；``group_id`` 留 0 表示这一条不生效。"""

    group_id: int = Field(default=0, description="群号，写纯数字，例如 123456789")
    enabled: bool = Field(default=True, description="这一群是否发送入群欢迎")
    template: str = Field(default="", description="这一群的欢迎语；留空沿用全局模板")
    leave_template: str = Field(default="", description="这一群的退群提示；留空沿用全局")


class Config(BaseModel):
    """插件配置；运行值在 ``plugins_data/group_welcome/config.toml``。"""

    enabled: bool = Field(default=True, description="总开关：关闭后所有群都不发欢迎")
    template: str = Field(
        default="欢迎 {at} 加入本群，记得先看群公告～",
        description="欢迎语模板，支持 {at} {name} {id} {group} {time} {date} {br} 等变量",
    )
    delay_seconds: float = Field(
        default=0.0,
        description="合并窗口（秒）：大于 0 时把这段时间内进群的人合并成一条，0 表示逐条立即发送",
    )
    leave_enabled: bool = Field(default=False, description="是否发送退群提示")
    leave_template: str = Field(default="{name} 离开了本群。", description="退群提示模板")
    groups: list[GroupRule] = Field(default_factory=list, description="按群定制（每个群一条）")


plugin = Plugin(
    "group_welcome",
    version="1.0.0",
    description="入群欢迎 / 退群提示：合并进群、按群定制模板、@ 新成员",
    author="NeoBot 第三方插件",
    config=Config,
)

# ── 运行期状态 ────────────────────────────────────────────────────
# 模块级即可：插件热重载会清掉模块缓存，状态随之复位。
_pending: dict[int, list[tuple[int, str]]] = {}
_flush_tasks: dict[int, asyncio.Task] = {}
_group_names: dict[int, str] = {}


# ── 小工具 ────────────────────────────────────────────────────────


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _rule_for(config: Config, group_id: int) -> GroupRule | None:
    for rule in config.groups or ():
        try:
            if int(rule.group_id) == group_id:
                return rule
        except (TypeError, ValueError):
            continue
    return None


def _effective_welcome(config: Config, rule: GroupRule | None) -> str:
    if rule is not None and rule.template.strip():
        return rule.template.strip()
    return (config.template or "").strip()


def _effective_leave(config: Config, rule: GroupRule | None) -> str:
    if rule is not None and rule.leave_template.strip():
        return rule.leave_template.strip()
    return (config.leave_template or "").strip()


def _pick(data: Any, *keys: str) -> str:
    """从字典 / 对象 / OneBot 的 {data: {...}} 信封里取第一个非空字符串。"""
    if data is None:
        return ""
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return _pick(data.get("data"), *keys)
    for key in keys:
        value = getattr(data, key, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _display_name(ctx, event: dict[str, Any], user_id: int, group_id: int) -> str:
    """优先用群名片，其次昵称，最后退回 QQ 号。"""
    try:
        profile = ctx.users.from_event(event)
        name = (getattr(profile, "card", None) or getattr(profile, "nickname", None) or "").strip()
        if name:
            return name
    except Exception:
        pass
    try:
        profile = await ctx.users.get(str(user_id), group_id=str(group_id))
        name = (profile.card or profile.nickname or "").strip()
        if name:
            return name
    except Exception:
        pass
    return str(user_id)


async def _group_name(ctx, group_id: int) -> str:
    """群名查一次就缓存；拿不到就退回群号，绝不让它拖垮欢迎语。"""
    cached = _group_names.get(group_id)
    if cached:
        return cached
    name = ""
    getter = getattr(getattr(ctx, "adapter", None), "get_group_info", None)
    if callable(getter):
        try:
            name = _pick(await getter(group_id), "group_name", "name")
        except Exception:
            name = ""
    name = name or str(group_id)
    _group_names[group_id] = name
    return name


def _compose(template: str, values: dict[str, str], user_ids: list[int]) -> MessageChain:
    """把模板渲染成消息链：文字段里插入 at 段，``{at}`` 可以出现在任意位置。"""
    rendered = _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), template)
    parts = rendered.split(_AT_MARK)
    chain = MessageChain()
    for index, part in enumerate(parts):
        if part:
            chain = chain.text(part)
        if index < len(parts) - 1:
            for uid in user_ids:
                chain = chain.at(str(uid))
    return chain


async def _build_chain(
    ctx,
    template: str,
    group_id: int,
    members: list[tuple[int, str]],
) -> MessageChain:
    user_ids = [uid for uid, _ in members]
    names = [name for _, name in members]
    now = datetime.now()
    needs_group = "{group}" in template or "{group_name}" in template
    group_name = await _group_name(ctx, group_id) if needs_group else str(group_id)
    values = {
        "at": _AT_MARK,
        "name": "、".join(names),
        "user": "、".join(names),
        "nickname": "、".join(names),
        "id": "、".join(str(uid) for uid in user_ids),
        "user_id": "、".join(str(uid) for uid in user_ids),
        "group": group_name,
        "group_name": group_name,
        "group_id": str(group_id),
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "clock": now.strftime("%H:%M:%S"),
        "bot": str(getattr(getattr(ctx, "adapter", None), "self_id", "") or ""),
        "br": "\n",
    }
    return _compose(template, values, user_ids)


async def _send(ctx, group_id: int, chain: MessageChain, what: str) -> None:
    try:
        await ctx.send_group(group_id, chain)
    except Exception as exc:  # 被禁言、被踢、风控……都不该把事件分发打挂
        ctx.logger.warning(f"[group_welcome] 群 {group_id} {what}发送失败: {type(exc).__name__}: {exc}")


# ── 合并进群 ──────────────────────────────────────────────────────


def _queue(ctx, group_id: int, template: str, user_id: int, name: str, delay: float) -> None:
    members = _pending.setdefault(group_id, [])
    for index, (uid, _old) in enumerate(members):
        if uid == user_id:
            members[index] = (user_id, name)
            break
    else:
        members.append((user_id, name))

    # 滑动窗口：每来一个人就重置计时，避免分批进群被拆成好几条
    task = _flush_tasks.get(group_id)
    if task is not None and not task.done():
        task.cancel()
    if len(members) >= _MAX_MERGE:
        delay = 0.0
    try:
        _flush_tasks[group_id] = ctx.create_task(
            _flush_later(ctx, group_id, template, delay),
            name=f"group_welcome-{group_id}",
        )
    except Exception as exc:  # 插件正在停止时 create_task 会抛
        _flush_tasks.pop(group_id, None)
        ctx.logger.warning(f"[group_welcome] 合并任务创建失败，改为立即发送: {type(exc).__name__}: {exc}")
        members = _pending.pop(group_id, [])
        if members:
            ctx.create_task(_send_now(ctx, group_id, template, members))


async def _flush_later(ctx, group_id: int, template: str, delay: float) -> None:
    if delay > 0:
        await asyncio.sleep(delay)
    members = _pending.pop(group_id, [])
    _flush_tasks.pop(group_id, None)
    if members:
        await _send_now(ctx, group_id, template, members)


async def _send_now(ctx, group_id: int, template: str, members: list[tuple[int, str]]) -> None:
    chain = await _build_chain(ctx, template, group_id, members)
    if len(chain) == 0:  # 模板渲染成空串（例如只剩空白），别发空消息
        return
    await _send(ctx, group_id, chain, "入群欢迎")


# ── 事件 ──────────────────────────────────────────────────────────


@plugin.event(post_type="notice", notice_type="group_increase")
async def on_group_increase(event: dict[str, Any], ctx, config: Config) -> None:
    """有人进群。"""
    try:
        await _handle_increase(event, ctx, config)
    except Exception as exc:
        ctx.logger.warning(f"[group_welcome] 入群欢迎处理失败: {type(exc).__name__}: {exc}")


async def _handle_increase(event: dict[str, Any], ctx, config: Config) -> None:
    if not config.enabled:
        return
    group_id = _to_int(event.get("group_id"))
    user_id = _to_int(event.get("user_id"))
    if group_id is None or user_id is None:
        return
    if user_id == _to_int(event.get("self_id")):
        return  # 机器人自己被拉进群，不用欢迎自己

    rule = _rule_for(config, group_id)
    if rule is not None and not rule.enabled:
        return
    template = _effective_welcome(config, rule)
    if not template:
        return

    name = await _display_name(ctx, event, user_id, group_id)
    delay = max(0.0, min(float(config.delay_seconds or 0.0), _MAX_DELAY))
    if delay > 0:
        _queue(ctx, group_id, template, user_id, name, delay)
        return
    await _send_now(ctx, group_id, template, [(user_id, name)])


@plugin.event(post_type="notice", notice_type="group_decrease")
async def on_group_decrease(event: dict[str, Any], ctx, config: Config) -> None:
    """有人退群 / 被踢。"""
    try:
        await _handle_decrease(event, ctx, config)
    except Exception as exc:
        ctx.logger.warning(f"[group_welcome] 退群提示处理失败: {type(exc).__name__}: {exc}")


async def _handle_decrease(event: dict[str, Any], ctx, config: Config) -> None:
    if not config.leave_enabled:
        return
    if str(event.get("sub_type") or "") == "kick_me":
        return  # 机器人自己被踢，这个群已经发不出消息了
    group_id = _to_int(event.get("group_id"))
    user_id = _to_int(event.get("user_id"))
    if group_id is None or user_id is None:
        return
    if user_id == _to_int(event.get("self_id")):
        return

    rule = _rule_for(config, group_id)
    if rule is not None and not rule.enabled:
        return
    template = _effective_leave(config, rule)
    if not template:
        return

    name = await _display_name(ctx, event, user_id, group_id)
    await _send_now(ctx, group_id, template, [(user_id, name)])


# ── 命令 ──────────────────────────────────────────────────────────

_HELP = (
    "入群欢迎用法：\n"
    "/欢迎 预览 —— 在本群按当前配置发一条示例\n"
    "/欢迎 状态 —— 查看本群的生效配置\n"
    "模板变量：{at} @新成员、{name} 昵称、{id} QQ号、{group} 群名、"
    "{group_id} 群号、{time} 时间、{date} 日期、{br} 换行"
)


def _status_text(config: Config, group_id: int) -> str:
    rule = _rule_for(config, group_id)
    template = _effective_welcome(config, rule)
    leave = _effective_leave(config, rule)
    lines = [
        f"群 {group_id} 的入群欢迎配置：",
        f"总开关：{'开' if config.enabled else '关'}",
        f"本群开关：{'开' if (rule is None or rule.enabled) else '关'}"
        f"{'（按群定制）' if rule is not None else '（未定制，用全局）'}",
        f"生效模板：{template or '（空，不会发送）'}",
        f"合并窗口：{float(config.delay_seconds or 0.0):g} 秒",
        f"退群提示：{'开' if config.leave_enabled else '关'} → {leave or '（空）'}",
    ]
    return "\n".join(lines)


@plugin.command(
    "欢迎 [action:rest]",
    permission=0,
    description="入群欢迎：预览 / 查看本群配置",
    aliases=("welcome", "入群欢迎"),
)
async def welcome_command(
    action: str | None,
    event: dict[str, Any],
    ctx,
    config: Config,
) -> str | None:
    text = (action or "").strip()
    group_id = _to_int(event.get("group_id"))
    if group_id is None:
        return "这个命令只能在群里用。"

    if text in {"预览", "preview", "测试"}:
        rule = _rule_for(config, group_id)
        template = _effective_welcome(config, rule)
        if not template:
            return "当前没有配置欢迎语模板。"
        user_id = _to_int(event.get("user_id")) or 0
        name = await _display_name(ctx, event, user_id, group_id) if user_id else "新成员"
        chain = await _build_chain(ctx, template, group_id, [(user_id, name)])
        try:
            await ctx.send_group(group_id, chain)
        except Exception as exc:
            return f"预览发送失败：{type(exc).__name__}: {exc}"
        return None

    if text in {"状态", "查看", "status"}:
        return _status_text(config, group_id)

    return _HELP


# ── 生命周期 ──────────────────────────────────────────────────────


@plugin.on_load
async def on_load(ctx) -> None:
    ctx.logger.info("[group_welcome] 已加载：入群欢迎 + 退群提示")


@plugin.on_shutdown
async def on_shutdown(ctx) -> None:
    for task in list(_flush_tasks.values()):
        task.cancel()
    _flush_tasks.clear()
    _pending.clear()
    ctx.logger.info("[group_welcome] 已停止")
