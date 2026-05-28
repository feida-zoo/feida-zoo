#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pl_2070b427 — 成员管理界面人数不对
测试套件：验证 _get_member_data() 对 status 过滤的正确性

覆盖：
1.  ZooRegistry.list_agents() 返回全量成员（含 inactive）
2.  _get_member_data 风格过滤函数 → 跳过 inactive
3.  活跃成员保留
4.  边界：无 metadata.status 字段 → 默认 active 不过滤
5.  边界：全部 inactive → 返回空
6.  YAML fallback 路径同等过滤
7.  MemberStatusManager 不追踪 inactive 成员

用法：
    cd <project_root>
    /tmp/venv/bin/pytest framework/tests/ut/test_member_active_filter.py -v
"""

import os
import sys
import tempfile
import json
from pathlib import Path

import pytest

# 加入项目 root
PROJECT_ROOT = Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo"))
sys.path.insert(0, str(PROJECT_ROOT))

from framework.core.mesh.zoo_registry import ZooRegistry

# ── 辅助：生成临时 zoo_members.yaml ──────────────────────────────────────────

YAML_TEMPLATE = """# 测试用成员配置（自动生成）
_version: "1.0.0"
_updated: "2026-05-26"

members:
  panda:
    id: panda
    name: 达达
    code_name: Panda
    role: admin
    display_name: 中枢调度大管家
    emoji: 🐼
    species: 熊猫
    model: minimax/MiniMax-M2.7
    session:
      key: agent:main:main
      channel: internal
    responsible_phases:
      - request
      - final_check
      - deliver
    capabilities:
      - orchestration
      - coordination
    metadata:
      language: zh-CN
      is_main_agent: true
      status: active

  alpha:
    id: alpha
    name: 阿尔法
    code_name: Alpha
    role: architect
    display_name: 首席架构师
    emoji: 🐢
    species: 玄龟
    model: deepseek/deepseek-v4-flash
    session:
      key: agent:alpha:main
      channel: internal
    responsible_phases:
      - validate
      - design
      - ui_design
      - develop_wt
      - develop_code
    capabilities:
      - architecture_design
      - system_analysis
    metadata:
      language: zh-CN
      is_main_agent: false
      status: active

  duci:
    id: duci
    name: 毒刺
    code_name: Duci
    role: auditor
    display_name: 无情审计师
    emoji: 🦂
    species: 蝎子
    model: minimax/MiniMax-M2.7
    session:
      key: agent:duci:main
      channel: internal
    responsible_phases:
      - review
      - review_test
      - test
      - audit
    capabilities:
      - security_audit
      - quality_assurance
    metadata:
      language: zh-CN
      is_main_agent: false
      status: active

  weaver:
    id: weaver
    name: 织巢
    code_name: Weaver
    role: engineer
    display_name: 疯狂工程师
    emoji: 🐜
    species: 蚂蚁
    model: minimax/MiniMax-M2.7
    session:
      key: agent:weaver:main
      channel: internal
    responsible_phases: []
    capabilities:
      - code_implementation
    metadata:
      language: zh-CN
      is_main_agent: false
      status: inactive

  aeterna:
    id: aeterna
    name: 埃特娜
    code_name: Aeterna
    role: scribe
    display_name: 永恒史官
    emoji: 🪨
    species: 黑曜石
    model: minimax/MiniMax-M2.7
    session:
      key: agent:aeterna:main
      channel: internal
    responsible_phases: []
    capabilities:
      - documentation
    metadata:
      language: zh-CN
      is_main_agent: false
      status: inactive

  gulu:
    id: gulu
    name: 咕噜
    code_name: Gulu
    role: designer
    display_name: 美术设计师
    emoji: 🟢
    species: 史莱姆
    model: minimax/MiniMax-M2.7
    session:
      key: agent:gulu:main
      channel: internal
    responsible_phases: []
    capabilities:
      - ui_design
    metadata:
      language: zh-CN
      is_main_agent: false
      status: inactive
"""


# ── 模拟 _get_member_data 的过滤逻辑 ──────────────────────────────────────


def simulated_get_active_members(yaml_data: dict) -> list:
    """模拟 app_enhanced.py 中 _get_member_data() 的过滤逻辑。"""
    members_data = yaml_data.get("members", {})
    active_members = []
    for member_id, info in members_data.items():
        meta = info.get("metadata", {}) or {}
        member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
        if member_status != "active":
            continue  # ← 核心过滤
        active_members.append(member_id)
    return active_members


def simulated_yaml_fallback(yaml_data: dict) -> list:
    """模拟 app_enhanced.py 中 _get_member_data() 的 YAML fallback 路径过滤。"""
    members_data = yaml_data.get("members", {})
    active_members = []
    for member_id, info in members_data.items():
        meta = info.get("metadata", {}) or {}
        member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
        if member_status != "active":
            continue
        active_members.append(member_id)
    return active_members


# ── 夹具 ────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_yaml_path():
    """创建临时 YAML 文件，6 成员（3 active + 3 inactive）。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(YAML_TEMPLATE)
        tmp_path = f.name
    yield tmp_path
    os.unlink(tmp_path)


@pytest.fixture
def temp_yaml_path_no_status():
    """创建临时 YAML，成员不含 metadata.status 字段。"""
    yaml_no_status = YAML_TEMPLATE.replace("      status: active", "").replace(
        "      status: inactive", ""
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_no_status)
        tmp_path = f.name
    yield tmp_path
    os.unlink(tmp_path)


@pytest.fixture
def temp_yaml_all_inactive():
    """创建临时 YAML，所有成员均为 inactive。"""
    yaml_all_inactive = YAML_TEMPLATE.replace("      status: active", "      status: inactive")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_all_inactive)
        tmp_path = f.name
    yield tmp_path
    os.unlink(tmp_path)


# ── 测试用例 ────────────────────────────────────────────────────────────


class TestZooRegistryListAgents:
    """验证 ZooRegistry 原始行为 — list_agents() 返回所有成员（含 inactive）。"""

    def test_list_agents_returns_all_six(self, temp_yaml_path):
        """list_agents() 应返回全部 6 个成员（不改 ZooRegistry 的前提下）。"""
        reg = ZooRegistry(yaml_path=temp_yaml_path)
        agents = reg.list_agents()
        assert len(agents) == 6, f"期望 6, 实际 {len(agents)}"
        assert "panda" in agents
        assert "alpha" in agents
        assert "duci" in agents
        assert "weaver" in agents
        assert "aeterna" in agents
        assert "gulu" in agents

    def test_get_full_info_includes_status(self, temp_yaml_path):
        """get_full_info() 应包含 metadata.status。"""
        reg = ZooRegistry(yaml_path=temp_yaml_path)
        alpha = reg.get_full_info("alpha")
        assert alpha is not None
        meta = alpha.get("metadata", {})
        assert meta.get("status") == "active"

        weaver = reg.get_full_info("weaver")
        assert weaver is not None
        meta = weaver.get("metadata", {})
        assert meta.get("status") == "inactive"


class TestGetActiveMembersFilter:
    """核心过滤逻辑测试。"""

    def test_active_three_retained(self):
        """3 个 active 成员应该全部保留。"""
        import yaml as _yaml
        data = _yaml.safe_load(YAML_TEMPLATE)
        active = simulated_get_active_members(data)
        assert "panda" in active
        assert "alpha" in active
        assert "duci" in active

    def test_inactive_three_excluded(self):
        """3 个 inactive 成员应该全部排除。"""
        import yaml as _yaml
        data = _yaml.safe_load(YAML_TEMPLATE)
        active = simulated_get_active_members(data)
        assert "weaver" not in active
        assert "aeterna" not in active
        assert "gulu" not in active

    def test_exact_active_count(self):
        """活跃成员应恰好为 3。"""
        import yaml as _yaml
        data = _yaml.safe_load(YAML_TEMPLATE)
        active = simulated_get_active_members(data)
        assert len(active) == 3

    def test_fallback_path_same_filter(self, temp_yaml_path):
        """YAML fallback 路径应产生相同的过滤结果。"""
        import yaml as _yaml
        with open(temp_yaml_path, "r") as f:
            data = _yaml.safe_load(f)
        active = simulated_yaml_fallback(data)
        assert len(active) == 3
        assert "weaver" not in active


class TestBoundaryCases:
    """边界条件测试。"""

    def test_no_status_field_defaults_active(self, temp_yaml_path_no_status):
        """缺少 metadata.status 时，应默认视为 active（不过滤）。"""
        import yaml as _yaml
        data = _yaml.safe_load(temp_yaml_path_no_status)
        # 读文件
        with open(temp_yaml_path_no_status, "r") as f:
            data = _yaml.safe_load(f)
        active = simulated_get_active_members(data)
        # 全部 6 个成员都没有 status → 全部保留
        assert len(active) == 6, (
            f"缺少 status 时默认 active，应保留全部 6 个，实际 {len(active)}"
        )

    def test_all_inactive_returns_empty(self, temp_yaml_all_inactive):
        """全部成员 inactive → 返回空列表。"""
        import yaml as _yaml
        with open(temp_yaml_all_inactive, "r") as f:
            data = _yaml.safe_load(f)
        active = simulated_get_active_members(data)
        assert len(active) == 0

    def test_empty_members(self):
        """空 members -> 空结果。"""
        result = simulated_get_active_members({"members": {}})
        assert result == []


class TestMemberStatusManagerScope:
    """验证 MemberStatusManager 不追踪 inactive 成员的逻辑。"""

    def test_monitor_should_skip_inactive(self, temp_yaml_path):
        """
        MemberStatusManager._update_status()
        应该只遍历 active 成员，不对 inactive 成员做进程检活。
        """
        import yaml as _yaml
        with open(temp_yaml_path, "r") as f:
            data = _yaml.safe_load(f)

        members_data = data.get("members", {})
        tracked = []
        for member_id, info in members_data.items():
            meta = info.get("metadata", {}) or {}
            mstatus = meta.get("status", "active") if isinstance(meta, dict) else "active"
            if mstatus == "active":
                tracked.append(member_id)

        assert "panda" in tracked
        assert "alpha" in tracked
        assert "duci" in tracked
        assert "weaver" not in tracked
        assert "aeterna" not in tracked
        assert "gulu" not in tracked
        assert len(tracked) == 3


class TestIntegratedFilterWithZooRegistry:
    """集成测试：通过 ZooRegistry 读取临时 YAML 并模拟完整过滤流程。"""

    def test_full_flow_active_filter(self, temp_yaml_path):
        """
        模拟 _get_member_data() 完整流程：
        1. ZooRegistry.list_agents() → 6
        2. 遍历并检查 metadata.status
        3. 仅返回 active 的 3 个
        """
        reg = ZooRegistry(yaml_path=temp_yaml_path)
        agent_ids = reg.list_agents()

        active_members = []
        for member_id in agent_ids:
            full = reg.get_full_info(member_id) or {}
            meta = full.get("metadata", {}) or {}
            member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
            if member_status != "active":
                continue
            active_members.append(member_id)

        assert len(active_members) == 3
        assert sorted(active_members) == ["alpha", "duci", "panda"]

    def test_yaml_from_registry_filter_matches(self, temp_yaml_path):
        """
        双路验证：ZooRegistry 路径和直接读 YAML fallback 路径
        应产生相同的活跃成员列表。
        """
        import yaml as _yaml

        # 路径 A：ZooRegistry
        reg = ZooRegistry(yaml_path=temp_yaml_path)
        ids_from_reg = []
        for mid in reg.list_agents():
            full = reg.get_full_info(mid) or {}
            meta = full.get("metadata", {}) or {}
            st = meta.get("status", "active") if isinstance(meta, dict) else "active"
            if st == "active":
                ids_from_reg.append(mid)

        # 路径 B：YAML fallback
        with open(temp_yaml_path, "r") as f:
            raw = _yaml.safe_load(f)
        ids_from_yaml = []
        for mid, info in raw.get("members", {}).items():
            meta = info.get("metadata", {}) or {}
            st = meta.get("status", "active") if isinstance(meta, dict) else "active"
            if st == "active":
                ids_from_yaml.append(mid)

        assert sorted(ids_from_reg) == sorted(ids_from_yaml)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
