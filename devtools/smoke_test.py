"""离线冒烟测试：不需要装 NeoBot / pydantic，用最小 stub 跑插件的核心逻辑。

跑法（仓库根目录或本目录都行）：

    python devtools/smoke_test.py

它验证的是**插件自己的逻辑**（模板渲染、合并窗口、按群定制、开关、命令），
不是 NeoBot 的装载器——装载与事件上报要在真机上验收。
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tomllib
import types
from datetime import datetime
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
PLUGIN_INIT = PLUGIN_DIR / "__init__.py"
PLUGIN_TOML = PLUGIN_DIR / "plugin.toml"


# ── stub: pydantic ────────────────────────────────────────────────


def _install_pydantic_stub() -> None:
    module = types.ModuleType("pydantic")

    class FieldInfo:
        def __init__(self, default=None, default_factory=None, description="", **kwargs):
            self.default = default
            self.default_factory = default_factory
            self.description = description

    def Field(default=None, *, default_factory=None, description="", **kwargs):
        return FieldInfo(default, default_factory, description)

    class BaseModel:
        __fields__: dict[str, object] = {}

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            fields: dict[str, object] = {}
            for base in reversed(cls.__mro__):
                for name in getattr(base, "__annotations__", {}):
                    if not name.startswith("_"):
                        fields[name] = getattr(base, name, None)
            cls.__fields__ = fields

        def __init__(self, **data):
            for name, default in type(self).__fields__.items():
                if name in data:
                    value = data[name]
                elif isinstance(default, FieldInfo):
                    value = default.default_factory() if default.default_factory else default.default
                else:
                    value = default
                setattr(self, name, value)
            for name, value in data.items():
                if name not in type(self).__fields__:
                    setattr(self, name, value)

        @classmethod
        def model_validate(cls, data):
            return cls(**dict(data))

    module.BaseModel = BaseModel
    module.Field = Field
    sys.modules["pydantic"] = module


# ── stub: neobot_modloader ────────────────────────────────────────


class FakeChain:
    """只记录消息段，够断言用。"""

    def __init__(self) -> None:
        self.parts: list[tuple[str, str]] = []

    def __len__(self) -> int:
        return len(self.parts)

    def text(self, value: str) -> "FakeChain":
        self.parts.append(("text", str(value)))
        return self

    def at(self, user_id: str) -> "FakeChain":
        self.parts.append(("at", str(user_id)))
        return self

    def plain(self) -> str:
        """只拼文字段；at 段单独用 ats() 断言。"""
        return "".join(value for kind, value in self.parts if kind == "text")

    def ats(self) -> list[str]:
        return [value for kind, value in self.parts if kind == "at"]


class FakePlugin:
    def __init__(self, name: str, **kwargs) -> None:
        self.name = name
        self.kwargs = kwargs
        self.events: list[dict] = []
        self.commands: list[dict] = []
        self.load_hooks: list = []
        self.shutdown_hooks: list = []

    def event(self, **kwargs):
        def decorate(handler):
            self.events.append({"options": kwargs, "handler": handler})
            return handler

        return decorate

    def command(self, pattern, **kwargs):
        def decorate(handler):
            self.commands.append({"pattern": pattern, "options": kwargs, "handler": handler})
            return handler

        return decorate

    def on_load(self, handler):
        self.load_hooks.append(handler)
        return handler

    def on_shutdown(self, handler):
        self.shutdown_hooks.append(handler)
        return handler


def _install_modloader_stub() -> None:
    module = types.ModuleType("neobot_modloader")
    module.MessageChain = FakeChain
    module.Plugin = FakePlugin
    sys.modules["neobot_modloader"] = module


def _install_identity_stub(group_map=None, user_map=None) -> None:
    """装一个假的 neobot_app.user_identity，模拟管理员用 /linkgroup 建过绑定。"""
    package = types.ModuleType("neobot_app")
    module = types.ModuleType("neobot_app.user_identity")
    groups = dict(group_map or {})
    users = dict(user_map or {})

    def group_number_for(group_id, channel=None):
        return groups.get(int(group_id))

    def qq_for_user(user_id, channel=None):
        return users.get(int(user_id))

    module.group_number_for = group_number_for
    module.qq_for_user = qq_for_user
    package.user_identity = module
    sys.modules["neobot_app"] = package
    sys.modules["neobot_app.user_identity"] = module


def _uninstall_identity_stub() -> None:
    sys.modules.pop("neobot_app.user_identity", None)
    sys.modules.pop("neobot_app", None)


# ── 假运行时对象 ──────────────────────────────────────────────────


class FakeLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message):
        self.lines.append(f"INFO {message}")

    def warning(self, message):
        self.lines.append(f"WARN {message}")

    def error(self, message):
        self.lines.append(f"ERROR {message}")


class FakeProfile:
    def __init__(self, user_id: str, nickname: str = "", card: str = "") -> None:
        self.user_id = user_id
        self.nickname = nickname
        self.card = card

    @property
    def display_name(self) -> str:
        return self.card or self.nickname or self.user_id


class FakeUsers:
    def __init__(self, profiles: dict[str, FakeProfile]) -> None:
        self._profiles = profiles

    def from_event(self, event):
        raise KeyError("sender")  # 模拟通知事件里没有 sender 字段

    async def get(self, user_id, *, group_id=None, refresh=False):
        profile = self._profiles.get(str(user_id))
        if profile is None:
            raise RuntimeError("查不到成员资料")
        return profile


class FakeAdapter:
    self_id = 10000

    def __init__(self, group_name: str = "测试群") -> None:
        self.group_name = group_name

    async def get_group_info(self, group_id):
        if self.group_name is None:
            raise RuntimeError("适配器不支持")
        return {"group_name": self.group_name}


class FakeCtx:
    def __init__(self, *, profiles=None, group_name="测试群") -> None:
        self.logger = FakeLogger()
        self.users = FakeUsers(profiles or {})
        self.adapter = FakeAdapter(group_name)
        self.sent: list[tuple[int, FakeChain]] = []
        self.tasks: list[asyncio.Task] = []

    async def send_group(self, group_id, chain):
        self.sent.append((int(group_id), chain))

    def create_task(self, coroutine, *, name=None):
        task = asyncio.create_task(coroutine, name=name)
        self.tasks.append(task)
        return task


# ── 载入插件 ──────────────────────────────────────────────────────


def load_plugin():
    _install_pydantic_stub()
    _install_modloader_stub()
    spec = importlib.util.spec_from_file_location("group_welcome_under_test", PLUGIN_INIT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_config(**overrides):
    assert _PLUGIN is not None
    data = {}
    for name, default in _PLUGIN.Config.__fields__.items():
        if hasattr(default, "default"):
            data[name] = default.default_factory() if default.default_factory else default.default
    data.update(overrides)
    return _PLUGIN.Config(**data)


def join_event(user_id=123, group_id=999, self_id=10000):
    return {
        "post_type": "notice",
        "notice_type": "group_increase",
        "sub_type": "approve",
        "group_id": group_id,
        "user_id": user_id,
        "self_id": self_id,
    }


def leave_event(user_id=123, group_id=999, self_id=10000, sub_type="leave"):
    return {
        "post_type": "notice",
        "notice_type": "group_decrease",
        "sub_type": sub_type,
        "group_id": group_id,
        "user_id": user_id,
        "self_id": self_id,
    }


# ── 用例 ──────────────────────────────────────────────────────────

_PLUGIN = None
_FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _FAILED
    if condition:
        print(f"  ok   {name}")
    else:
        _FAILED += 1
        print(f"  FAIL {name} {detail}")


async def case_single_welcome() -> None:
    print("单条欢迎 + 变量渲染")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    config = make_config(template="欢迎 {at} 加入 {group}！{name}({id}) {date}")
    await _PLUGIN.on_group_increase(join_event(), ctx, config)

    check("发了一条", len(ctx.sent) == 1)
    chain = ctx.sent[0][1]
    check("@ 了新成员", chain.ats() == ["123"], str(chain.parts))
    plain = chain.plain()
    check("群名替换", "测试群" in plain, plain)
    check("昵称替换", "小明" in plain, plain)
    check("QQ 号替换", "(123)" in plain, plain)
    check("日期替换", datetime.now().strftime("%Y-%m-%d") in plain, plain)
    check("没有残留占位符", "{" not in plain, plain)


async def case_unknown_placeholder() -> None:
    print("未知占位符保持原样")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    config = make_config(template="你好 {at}{unknown}")
    await _PLUGIN.on_group_increase(join_event(), ctx, config)
    check("{unknown} 原样保留", "{unknown}" in ctx.sent[0][1].plain(), ctx.sent[0][1].plain())


async def case_br() -> None:
    print("{br} 换行")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    config = make_config(template="第一行{br}第二行{at}")
    await _PLUGIN.on_group_increase(join_event(), ctx, config)
    check("插入换行", "第一行\n第二行" in ctx.sent[0][1].plain(), ctx.sent[0][1].plain())


async def case_merge() -> None:
    print("合并窗口：3 个人 → 1 条消息")
    ctx = FakeCtx(
        profiles={
            "1": FakeProfile("1", nickname="甲"),
            "2": FakeProfile("2", nickname="乙"),
            "3": FakeProfile("3", nickname="丙"),
        }
    )
    config = make_config(delay_seconds=0.3, template="欢迎 {at}（{name}）")
    for uid in (1, 2, 3):
        await _PLUGIN.on_group_increase(join_event(user_id=uid), ctx, config)
    check("窗口内先不发", len(ctx.sent) == 0)
    await asyncio.sleep(0.6)
    check("只发一条", len(ctx.sent) == 1, str(len(ctx.sent)))
    chain = ctx.sent[0][1]
    check("三个 @", chain.ats() == ["1", "2", "3"], str(chain.ats()))
    check("名字用顿号合并", "甲、乙、丙" in chain.plain(), chain.plain())


async def case_group_rule() -> None:
    print("按群定制 / 按群关闭")
    rule = _PLUGIN.GroupRule(group_id=999, template="定制欢迎 {at}")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    config = make_config(groups=[rule])
    await _PLUGIN.on_group_increase(join_event(), ctx, config)
    check("用了定制模板", ctx.sent[0][1].plain() == "定制欢迎 ", ctx.sent[0][1].plain())

    other = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_increase(join_event(group_id=888), other, config)
    check("别的群用全局模板", "记得先看群公告" in other.sent[0][1].plain(), other.sent[0][1].plain())

    off = _PLUGIN.GroupRule(group_id=999, enabled=False)
    silent = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_increase(join_event(), silent, make_config(groups=[off]))
    check("关掉的群不发", len(silent.sent) == 0)


async def case_switches() -> None:
    print("总开关 / 机器人自己进群 / 空模板")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_increase(join_event(), ctx, make_config(enabled=False))
    check("总开关关闭不发", len(ctx.sent) == 0)

    ctx2 = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_increase(join_event(user_id=10000), ctx2, make_config())
    check("机器人自己进群不发", len(ctx2.sent) == 0)

    ctx3 = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_increase(join_event(), ctx3, make_config(template="   "))
    check("空模板不发", len(ctx3.sent) == 0)


async def case_leave() -> None:
    print("退群提示")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_decrease(leave_event(), ctx, make_config(leave_enabled=False))
    check("默认不发退群", len(ctx.sent) == 0)

    ctx2 = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_decrease(leave_event(), ctx2, make_config(leave_enabled=True))
    check("开启后发退群", len(ctx2.sent) == 1)
    check("退群模板生效", "小明 离开了本群。" == ctx2.sent[0][1].plain(), ctx2.sent[0][1].plain())

    ctx3 = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    await _PLUGIN.on_group_decrease(
        leave_event(sub_type="kick_me"), ctx3, make_config(leave_enabled=True)
    )
    check("机器人被踢不发", len(ctx3.sent) == 0)


async def case_command() -> None:
    print("命令：状态 / 预览 / 帮助")
    ctx = FakeCtx(profiles={"123": FakeProfile("123", nickname="小明")})
    config = make_config()

    status = await _PLUGIN.welcome_command("状态", {"group_id": 999, "user_id": 123}, ctx, config)
    check("状态含模板", "生效模板" in (status or ""), status or "")
    check("状态含群号", "999" in (status or ""), status or "")

    await _PLUGIN.welcome_command("预览", {"group_id": 999, "user_id": 123}, ctx, config)
    check("预览发到群里", len(ctx.sent) == 1)
    check("预览 @ 了操作者", ctx.sent[0][1].ats() == ["123"])

    help_text = await _PLUGIN.welcome_command("", {"group_id": 999, "user_id": 123}, ctx, config)
    check("帮助列出变量", "{at}" in (help_text or ""), help_text or "")

    private = await _PLUGIN.welcome_command("状态", {"user_id": 123}, ctx, config)
    check("私聊提示只能在群里用", "只能在群里用" in (private or ""), private or "")


def case_toml() -> None:
    print("plugin.toml 与配置模型一致")
    data = tomllib.loads(PLUGIN_TOML.read_text(encoding="utf-8"))
    check("name 一致", data["name"] == _PLUGIN.plugin.name, str(data.get("name")))
    check(
        "version 一致",
        data["version"] == _PLUGIN.plugin.kwargs.get("version"),
        f'{data.get("version")} vs {_PLUGIN.plugin.kwargs.get("version")}',
    )
    config_keys = set(data.get("config", {}))
    model_keys = set(_PLUGIN.Config.__fields__)
    check("配置键都在模型里", config_keys <= model_keys, str(config_keys - model_keys))
    try:
        _PLUGIN.Config()
        empty_ok = True
    except Exception as exc:  # 所有字段都必须有默认值，否则面板/默认值会崩
        empty_ok = False
        detail = f"{type(exc).__name__}: {exc}"
    check("空配置可构造（字段都有默认值）", empty_ok, "" if empty_ok else detail)


async def case_official_ids() -> None:
    print("官方通道：合成 ID ↔ 真实群号 / QQ 映射")
    synthetic_group = 9_500_000_000_000
    synthetic_user = 9_000_000_000_001
    _install_identity_stub(
        group_map={synthetic_group: 123456789},
        user_map={synthetic_user: 88888888},
    )
    try:
        ctx = FakeCtx(profiles={str(synthetic_user): FakeProfile(str(synthetic_user), nickname="小明")})
        rule = _PLUGIN.GroupRule(group_id=123456789, template="定制 {at} {id} 进 {group_id}")
        await _PLUGIN.on_group_increase(
            join_event(user_id=synthetic_user, group_id=synthetic_group),
            ctx,
            make_config(groups=[rule]),
        )
        check("配置写真实群号也能命中", len(ctx.sent) == 1, str(len(ctx.sent)))
        chain = ctx.sent[0][1]
        check("@ 仍用合成 ID（协议要求）", chain.ats() == [str(synthetic_user)], str(chain.ats()))
        check("{id} 显示真实 QQ", "88888888" in chain.plain(), chain.plain())
        check("{group_id} 显示真实群号", "123456789" in chain.plain(), chain.plain())

        ctx2 = FakeCtx(profiles={str(synthetic_user): FakeProfile(str(synthetic_user))})
        cfg2 = make_config(template="原始 {raw_group_id}")
        await _PLUGIN.on_group_increase(
            join_event(user_id=synthetic_user, group_id=synthetic_group), ctx2, cfg2
        )
        check("{raw_group_id} 保持合成号", str(synthetic_group) in ctx2.sent[0][1].plain(), ctx2.sent[0][1].plain())

        status = await _PLUGIN.welcome_command("状态", {"group_id": synthetic_group, "user_id": 1}, ctx2, cfg2)
        check("状态显示已绑定", "已绑定真实群号 123456789" in (status or ""), status or "")
    finally:
        _uninstall_identity_stub()

    # 没有 user_identity 模块（纯 OneBot / 未绑定）时不能崩
    ctx3 = FakeCtx()
    await _PLUGIN.on_group_increase(join_event(group_id=999, user_id=123), ctx3, make_config(template="欢迎 {at} {group_id}"))
    check("无映射模块照常工作", bool(ctx3.sent) and "999" in ctx3.sent[0][1].plain(), "no send")


async def main() -> int:
    global _PLUGIN
    _PLUGIN = load_plugin()

    check("插件名", _PLUGIN.plugin.name == "group_welcome", _PLUGIN.plugin.name)
    check("注册了 2 个事件", len(_PLUGIN.plugin.events) == 2, str(len(_PLUGIN.plugin.events)))
    notice_types = sorted(item["options"].get("notice_type", "") for item in _PLUGIN.plugin.events)
    check(
        "订阅 group_increase / group_decrease",
        notice_types == ["group_decrease", "group_increase"],
        str(notice_types),
    )
    check("注册了命令", len(_PLUGIN.plugin.commands) == 1)
    command = _PLUGIN.plugin.commands[0]
    check("命令要权限 0", command["options"].get("permission") == 0, str(command["options"]))

    case_toml()
    await case_single_welcome()
    await case_unknown_placeholder()
    await case_br()
    await case_merge()
    await case_group_rule()
    await case_switches()
    await case_leave()
    await case_command()
    await case_official_ids()

    print()
    if _FAILED:
        print(f"FAILED: {_FAILED} 项")
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
