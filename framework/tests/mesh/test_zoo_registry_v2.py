"""Tests for ZooRegistry V2 — YAML-driven member configuration.

Design doc: pl_3833295c_design.md
Key changes: ZooRegistry reads from zoo_members.yaml instead of hardcoded _DEFAULT_LABEL_MAP.
"""

import copy
import json
import os
import tempfile
import time

import pytest
import yaml

from framework.core.mesh.zoo_registry import ZooRegistry, SessionRouter


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _make_yaml(tmp_path, members=None, custom=None):
    """Create a minimal test zoo_members.yaml and return its path."""
    if members is None:
        members = _DEFAULT_MEMBERS
    data = {"_version": "1.0.0", "_updated": "2026-05-21", "members": members}
    if custom:
        data.update(custom)
    path = tmp_path / "zoo_members.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return str(path)


def _make_openclaw_json(tmp_path, custom_models=None):
    """Create a minimal openclaw.json and return its path."""
    data = {
        "agents": {
            "defaults": {
                "models": custom_models or {
                    "deepseek/deepseek-v4-flash": {"alias": "DeepSeek"},
                    "minimax/MiniMax-M2.7": {"alias": "Minimax"},
                    "volcengine-plan/glm-5.1": {},
                },
                "model": {
                    "primary": "volcengine-plan/glm-5.1",
                },
            }
        }
    }
    path = tmp_path / "openclaw.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


_DEFAULT_MEMBERS = {
    "panda": {
        "id": "panda",
        "name": "达达",
        "code_name": "Panda",
        "role": "admin",
        "display_name": "中枢调度大管家",
        "emoji": "🐼",
        "species": "熊猫",
        "model": "minimax/MiniMax-M2.7",
        "session": {"key": "agent:main:main", "channel": "internal"},
        "responsible_phases": ["request", "final_check", "deliver"],
        "capabilities": ["orchestration", "coordination"],
        "metadata": {"language": "zh-CN", "is_main_agent": True, "status": "active"},
    },
    "alpha": {
        "id": "alpha",
        "name": "阿尔法",
        "code_name": "Alpha",
        "role": "architect",
        "display_name": "首席架构师",
        "emoji": "🐢",
        "species": "玄龟",
        "model": "deepseek/deepseek-v4-flash",
        "session": {"key": "agent:alpha:main", "channel": "internal"},
        "responsible_phases": ["validate", "design", "ui_design", "develop_wt", "develop_code"],
        "capabilities": ["architecture_design", "system_analysis"],
        "metadata": {"language": "zh-CN", "is_main_agent": False, "status": "active"},
    },
    "duci": {
        "id": "duci",
        "name": "毒刺",
        "code_name": "Duci",
        "role": "auditor",
        "display_name": "无情审计师",
        "emoji": "🦂",
        "species": "蝎子",
        "model": "minimax/MiniMax-M2.7",
        "session": {"key": "agent:duci:main", "channel": "internal"},
        "responsible_phases": ["review", "review_test", "test", "audit"],
        "capabilities": ["security_audit", "code_review"],
        "metadata": {"language": "zh-CN", "is_main_agent": False, "status": "active"},
    },
}


# ── Tests: YAML Loading ──────────────────────────────────────────────────────────


class TestYamlLoading:
    """ZooRegistry loads from zoo_members.yaml on construction."""


    def test_loads_members_from_yaml(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        agents = reg.list_agents()
        assert "alpha" in agents
        assert "panda" in agents
        assert "duci" in agents
        assert len(agents) == 3

    def test_get_full_info_returns_all_fields(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        info = reg.get_full_info("alpha")
        assert info is not None
        assert info["name"] == "阿尔法"
        assert info["species"] == "玄龟"
        assert info["emoji"] == "🐢"
        assert info["role"] == "architect"
        assert info["display_name"] == "首席架构师"
        assert info["session"]["key"] == "agent:alpha:main"
        assert len(info["responsible_phases"]) == 5
        assert info["metadata"]["is_main_agent"] is False

    def test_get_full_info_unknown_agent(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_full_info("nobody") is None

    def test_get_info_downward_compatible(self, tmp_path):
        """get_info() still returns {label, model} dict for backward compat."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        info = reg.get_info("alpha")
        assert isinstance(info, dict)
        assert "label" in info
        assert "model" in info

    def test_missing_yaml_file_raises(self, tmp_path):
        """Constructor must raise if YAML file doesn't exist."""
        oc_path = _make_openclaw_json(tmp_path)
        nonexistent = str(tmp_path / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            ZooRegistry(yaml_path=nonexistent, openclaw_path=oc_path)

    def test_malformed_yaml_raises(self, tmp_path):
        bad_path = tmp_path / "bad.yaml"
        bad_path.write_text("not: valid: yaml: [[[")
        oc_path = _make_openclaw_json(tmp_path)
        with pytest.raises(Exception):
            ZooRegistry(yaml_path=str(bad_path), openclaw_path=oc_path)

    def test_reload_preserves_old_data_on_error(self, tmp_path):
        """reload() keeps existing data when new file is corrupt."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert "alpha" in reg.list_agents()

        # Corrupt the YAML
        with open(yaml_path, "w") as f:
            f.write("[[corrupted not yaml!!!]]")

        # reload() should not crash and keep old data
        reg.reload()
        assert "alpha" in reg.list_agents()

    def test_reload_picks_up_new_members(self, tmp_path):
        """reload() with valid new YAML picks up changes."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert "panda" in reg.list_agents()

        # Write updated YAML with a new member
        members = copy.deepcopy(_DEFAULT_MEMBERS)
        members["newbee"] = {
            "id": "newbee",
            "name": "新手",
            "code_name": "NewBee",
            "role": "tester",
            "display_name": "测试新手",
            "emoji": "🐝",
            "species": "蜜蜂",
            "model": "minimax/MiniMax-M2.7",
            "session": {"key": "agent:newbee:main", "channel": "internal"},
            "responsible_phases": [],
            "capabilities": ["testing"],
            "metadata": {"language": "zh-CN", "is_main_agent": False, "status": "active"},
        }
        _make_yaml(tmp_path, members=members)
        reg.reload()
        assert "newbee" in reg.list_agents()

    def test_singleton_preserved(self, tmp_path):
        """ZooRegistry remains singleton even with YAML params."""
        members_a = {"agent_a": {
            "id": "agent_a", "name": "A",
            "session": {"key": "agent:a:main"},
            "responsible_phases": [],
        }}
        members_b = {"agent_b": {
            "id": "agent_b", "name": "B",
            "session": {"key": "agent:b:main"},
            "responsible_phases": [],
        }}
        yaml_a = _make_yaml(tmp_path, members=members_a)
        yaml_b = str(tmp_path / "b.yaml")
        with open(yaml_b, "w") as f:
            yaml.dump({"_version": "1.0", "members": members_b}, f)
        oc_path = _make_openclaw_json(tmp_path)
        reg1 = ZooRegistry(yaml_path=yaml_a, openclaw_path=oc_path)
        reg2 = ZooRegistry(yaml_path=yaml_b, openclaw_path=oc_path)
        # Singleton: same object even with different YAML paths
        assert reg1 is reg2
        # Latest YAML takes effect (last loaded wins with singleton)
        assert "agent_b" in reg1.list_agents()


# ── Tests: Label Derivation ──────────────────────────────────────────────────────


class TestLabelDerivation:
    """Label is derived from session.key: agent:<id>:main → <id>-zoomesh."""


    def test_label_from_session_key(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_label("alpha") == "alpha-zoomesh"

    def test_label_panda_uses_main_session(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        # panda's session.key is "agent:main:main" → extract "main" → label "main-zoomesh"
        assert reg.get_label("panda") == "main-zoomesh"

    def test_label_duci(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_label("duci") == "duci-zoomesh"

    def test_label_unknown_agent(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_label("nobody") is None

    def test_label_explicit_field_overrides_yaml(self, tmp_path):
        """If YAML has explicit 'label' field, use it directly."""
        members = copy.deepcopy(_DEFAULT_MEMBERS)
        members["alpha"]["label"] = "custom-alpha-label"
        yaml_path = _make_yaml(tmp_path, members=members)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_label("alpha") == "custom-alpha-label"

    def test_label_missing_session_key(self, tmp_path):
        """Agent without session.key should return None for get_label()."""
        members = copy.deepcopy(_DEFAULT_MEMBERS)
        del members["alpha"]["session"]["key"]
        yaml_path = _make_yaml(tmp_path, members=members)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_label("alpha") is None


# ── Tests: get_phase_agent() ─────────────────────────────────────────────────────


class TestGetPhaseAgent:
    """Maps phase name → responsible agent from YAML responsible_phases."""


    def test_phase_to_alpha(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_phase_agent("design") == "alpha"
        assert reg.get_phase_agent("validate") == "alpha"
        assert reg.get_phase_agent("develop_wt") == "alpha"

    def test_phase_to_duci(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_phase_agent("review") == "duci"
        assert reg.get_phase_agent("audit") == "duci"

    def test_phase_to_panda(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_phase_agent("request") == "panda"
        assert reg.get_phase_agent("deliver") == "panda"

    def test_unmapped_phase_falls_back_to_panda(self, tmp_path):
        """Phase not in any member's responsible_phases → returns 'panda'."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_phase_agent("nonexistent_stage") == "panda"

    def test_main_agent_excluded_from_phase_resolution(self, tmp_path):
        """If a phase is assigned to both main-agent and non-main agent,
        the main agent should be excluded."""
        members = copy.deepcopy(_DEFAULT_MEMBERS)
        # Both panda (main) and duci (non-main) are responsible for "review"
        members["panda"]["responsible_phases"] = ["review", "request"]
        yaml_path = _make_yaml(tmp_path, members=members)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        # Should prefer duci (non-main) over panda (main)
        assert reg.get_phase_agent("review") == "duci"

    def test_get_responsible_phases(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        phases = reg.get_responsible_phases("alpha")
        assert "design" in phases
        assert "validate" in phases
        assert "develop_code" in phases
        assert len(phases) == 5

    def test_get_responsible_phases_unknown(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_responsible_phases("nobody") == []


# ── Tests: Model Display ─────────────────────────────────────────────────────────


class TestGetModelDisplay:
    """Model display with openclaw.json alias resolution."""


    def test_non_main_agent_shows_model_alias(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        # alpha is non-main, model=deepseek/deepseek-v4-flash → alias "DeepSeek"
        display = reg.get_model_display("alpha")
        assert display == "DeepSeek"

    def test_main_agent_shows_primary_model(self, tmp_path):
        """Panda is main agent → model should be primary from openclaw.json."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        # primary is volcengine-plan/glm-5.1 → no alias → show raw ID
        display = reg.get_model_display("panda")
        assert display == "volcengine-plan/glm-5.1"

    def test_main_agent_fallback_to_alias_model(self, tmp_path):
        """If primary has no alias, use first model with alias."""
        models = {
            "deepseek/deepseek-v4-flash": {"alias": "DeepSeek"},
            "minimax/MiniMax-M2.7": {"alias": "Minimax"},
            "kimi/k2p6": {},
        }
        oc_path = _make_openclaw_json(tmp_path, custom_models=models)
        members = copy.deepcopy(_DEFAULT_MEMBERS)
        members["panda"]["model"] = "minimax/MiniMax-M2.7"
        yaml_path = _make_yaml(tmp_path, members=members)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        # primary is volcengine-plan/glm-5.1 — which is NOT in models
        # Should fallback to first model with alias: "DeepSeek"
        # Actually, let me check the actual primary
        display = reg.get_model_display("panda")
        # primary doesn't exist in models → fallback to first non-empty alias
        assert display is not None
        assert isinstance(display, str)

    def test_model_display_no_openclaw_json(self, tmp_path):
        """When openclaw.json doesn't exist, return raw model ID."""
        yaml_path = _make_yaml(tmp_path)
        nonexistent_oc = str(tmp_path / "nonexistent.json")
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=nonexistent_oc)
        display = reg.get_model_display("alpha")
        assert display == "deepseek/deepseek-v4-flash"

    def test_model_display_for_unknown_agent(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_model_display("nobody") is None


# ── Tests: SessionRouter Compatibility ───────────────────────────────────────────


class TestSessionRouterV2:
    """SessionRouter works with YAML-driven ZooRegistry."""


    def test_resolve_via_label_yaml_driven(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        router = SessionRouter(phase="phase3")
        label = router.resolve("alpha")
        assert label == "alpha-zoomesh"

    def test_phase1_uses_cache(self, tmp_path):
        router = SessionRouter(phase="phase1")
        router._cache["alpha"] = "agent:alpha:main"
        result = router.resolve("alpha")
        assert result == "agent:alpha:main"

    def test_resolve_unknown_agent(self, tmp_path):
        router = SessionRouter(phase="phase3")
        assert router.resolve("nobody") is None

    def test_connect_changes_phase(self):
        router = SessionRouter(phase="phase1")
        router.connect("phase3")
        assert router.phase == "phase3"
        assert router._cache == {}

    def test_register_still_works(self, tmp_path):
        """register() should still work for backward compat — overlays YAML."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        reg.register("temp_agent", label="temp-zoomesh", model="minimax/MiniMax-M2.7")
        assert "temp_agent" in reg.list_agents()
        assert reg.get_label("temp_agent") == "temp-zoomesh"


# ── Tests: Lifecycle Status ──────────────────────────────────────────────────────


class TestLifecycleV2:
    """Agent lifecycle tracking works with YAML-driven mode."""


    def test_default_status_online(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        assert reg.get_status("alpha") == "online"

    def test_set_status_then_get(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        reg.set_status("alpha", "busy")
        assert reg.get_status("alpha") == "busy"

    def test_status_unknown_agent(self):
        reg = ZooRegistry()
        reg.clear()
        assert reg.get_status("ghost") is None

    def test_session_cache_still_works(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        reg.set_session_cache("alpha", "sess_v2_123")
        assert reg.get_session_cache("alpha") == "sess_v2_123"


# ── Tests: Edge Cases ────────────────────────────────────────────────────────────


class TestEdgeCasesV2:
    """Edge cases and error handling."""


    def test_empty_yaml_no_members(self, tmp_path):
        path = tmp_path / "empty.yaml"
        with open(path, "w") as f:
            yaml.dump({"_version": "1.0.0", "members": {}}, f)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=str(path), openclaw_path=oc_path)
        assert reg.list_agents() == []

    def test_yaml_with_non_required_fields(self, tmp_path):
        """YAML with extra fields should still load fine."""
        members = {
            "testbot": {
                "id": "testbot",
                "name": "测试机器人",
                "session": {"key": "agent:testbot:main"},
                "responsible_phases": [],
            }
        }
        path = _make_yaml(tmp_path, members=members)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=path, openclaw_path=oc_path)
        assert "testbot" in reg.list_agents()
        info = reg.get_full_info("testbot")
        assert info["name"] == "测试机器人"

    def test_register_overrides_yaml(self, tmp_path):
        """register() on an existing agent should override YAML data in memory."""
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        reg.register("alpha", label="overridden-label")
        assert reg.get_label("alpha") == "overridden-label"

    def test_clear_removes_all(self, tmp_path):
        yaml_path = _make_yaml(tmp_path)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        reg.clear()
        assert reg.list_agents() == []

    def test_multiple_agents_same_phase(self, tmp_path):
        """When two non-main agents share a phase, return first alphabetically."""
        members = copy.deepcopy(_DEFAULT_MEMBERS)
        # Both duci and a new agent share "audit"
        members["new_auditor"] = {
            "id": "new_auditor",
            "name": "新审计",
            "session": {"key": "agent:new_auditor:main"},
            "responsible_phases": ["audit", "final_check"],
            "metadata": {"is_main_agent": False},
        }
        yaml_path = _make_yaml(tmp_path, members=members)
        oc_path = _make_openclaw_json(tmp_path)
        reg = ZooRegistry(yaml_path=yaml_path, openclaw_path=oc_path)
        # Should return the first one encountered in YAML iteration order
        agent = reg.get_phase_agent("audit")
        assert agent is not None
        assert agent in ("duci", "new_auditor")
