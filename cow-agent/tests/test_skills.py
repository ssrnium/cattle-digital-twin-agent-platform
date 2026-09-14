"""领域 Skills 发现验证：AGENT_HOME/.bear/skills 下的 4 个 SKILL.md 被母版 skills 模块发现。"""
from pathlib import Path

from app.patch import BEAR_ROOT  # noqa: F401  # 触发 sys.path 注入
import agents.skills as skills_mod

AGENT_HOME = Path(__file__).resolve().parent.parent / "agent-home"

EXPECTED = {"mounting-review", "lameness-check", "device-offline", "report-style"}


def test_discover_domain_skills(monkeypatch):
    monkeypatch.chdir(AGENT_HOME)
    skills_mod.reset_skill_cache()
    found = {s.name: s for s in skills_mod.discover_skills()}
    assert EXPECTED <= set(found), f"缺少领域 skills: {EXPECTED - set(found)}"
    for name in EXPECTED:
        assert found[name].description, name
        assert found[name].when_to_use, name
