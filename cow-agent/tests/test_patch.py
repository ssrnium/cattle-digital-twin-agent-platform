"""patch.py 生效验证：check_permission 扩展、print_* no-op、后台进化关闭。"""
import os

from app.patch import apply_patches


def test_apply_patches_idempotent():
    apply_patches()
    apply_patches()  # 重复应用不报错


def test_write_tool_requires_confirm():
    apply_patches()
    import agents.agent as agent_mod

    perm = agent_mod.check_permission(
        "create_work_order", {"type": "VET_CHECK", "description": "x"}, "default", None)
    assert perm["action"] == "confirm"
    assert "cow_write" in perm["message"]


def test_readonly_tools_auto_allowed():
    apply_patches()
    import agents.agent as agent_mod

    for name in ("query_cow_profile", "list_events", "list_devices"):
        # 领域只读工具不在母版 READ_TOOLS 里，但也未被规则拒绝 → 回落 allow
        perm = agent_mod.check_permission(name, {}, "default", None)
        assert perm["action"] == "allow", name


def test_ui_prints_are_noop():
    apply_patches()
    import agents.agent as agent_mod

    assert agent_mod.print_info("hello") is None
    assert agent_mod.start_spinner() is None
    assert agent_mod.stop_spinner() is None


def test_skill_evolution_disabled():
    apply_patches()
    assert os.environ.get("BEAR_AUTO_SKILL_EVOLUTION") == "0"
