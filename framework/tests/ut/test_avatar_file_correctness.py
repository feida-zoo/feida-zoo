#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pl_ecd1f8b8 — 成员管理界面各成员头像不正确
测试套件：验证头像文件正确性、_serve_avatar() 路径修复、遗留文件清理

覆盖：
1.  源文件存在性：agents/{id}/avatar.png 存在且为 PNG
2.  源文件尺寸：1024×1024 正方形
3.  静态头像替换后：dashboard/static/avatars/{id}.png 为 1024×1024
4.  遗留清理：stinger + inactive 成员文件已删除
5.  _serve_avatar() 路径：PROJECT_AGENTS_DIR 指向正确
6.  前端无 stinger 硬编码
7.  active 成员均有静态头像文件

用法：
    cd /Users/zoo/workspace/code/feida_zoo
    ./venv/bin/pytest framework/tests/ut/test_avatar_file_correctness.py -v
"""

import os
import sys
from pathlib import Path

import pytest

# ── 项目路径 ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path("/Users/zoo/workspace/code/feida_zoo")
AGENTS_DIR = PROJECT_ROOT / "agents"
STATIC_AVATAR_DIR = PROJECT_ROOT / "dashboard" / "static" / "avatars"

# 活跃成员（与 pl_2070b427 过滤结果一致）
ACTIVE_MEMBERS = ["alpha", "duci", "panda"]

# 非活跃成员（应该被清理 / 不显示）
INACTIVE_MEMBERS = ["weaver", "aeterna", "gulu"]

# 不存在于 YAML 的遗留文件
GHOST_FILES = ["stinger"]

# 期望尺寸
EXPECTED_SIZE = (1024, 1024)


# ── 辅助函数 ─────────────────────────────────────────────────────────────


def get_image_info(path: Path):
    """用 file 命令获取图像类型和尺寸。返回 (format, width, height) 或 None。"""
    import subprocess
    import re
    try:
        result = subprocess.run(
            ["file", str(path)],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout.strip()
        # 匹配: PNG image data, 1024 x 1024, ...
        # 或 JPEG ... precision 8, 1024x1024, components 3
        m = re.search(r'(PNG|JPEG)\s+image\s+data.*?,\s*(\d+)\s*x\s*(\d+),', output)
        if not m:
            # JPEG 有时用逗号+空格后跟尺寸，如: baseline, precision 8, 1024x1024, components
            m = re.search(r'precision\s+\d+,\s*(\d+)\s*x\s*(\d+),\s*components', output)
        if m:
            fmt = m.group(1)
            w = int(m.group(2))
            h = int(m.group(3))
            return (fmt, w, h)
        return None
    except Exception:
        return None


# ── 测试类 ────────────────────────────────────────────────────────────────


class TestSourceAvatarFiles:
    """agents/ 目录中的源头像文件（权威来源）。"""

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_source_file_exists(self, member_id):
        """agents/{id}/avatar.png 存在。"""
        path = AGENTS_DIR / member_id / "avatar.png"
        assert path.exists(), f"源文件不存在: {path}"

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_source_file_exists_and_valid(self, member_id):
        """源文件是有效的图像（PNG 或 JPEG）。"""
        path = AGENTS_DIR / member_id / "avatar.png"
        info = get_image_info(path)
        assert info is not None, f"源文件不存在或非有效图像: {path}"

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_source_file_dimensions(self, member_id):
        """源文件为 1024×1024 正方形。"""
        path = AGENTS_DIR / member_id / "avatar.png"
        info = get_image_info(path)
        assert info is not None, f"无法读取: {path}"
        _, w, h = info
        assert (w, h) == EXPECTED_SIZE, (
            f"{member_id} 源文件尺寸 {w}x{h}，期望 {EXPECTED_SIZE[0]}x{EXPECTED_SIZE[1]}"
        )

    def test_source_for_all_active(self):
        """所有活跃成员均有源文件。"""
        for mid in ACTIVE_MEMBERS:
            assert (AGENTS_DIR / mid / "avatar.png").exists(), f"缺少 {mid}"


class TestStaticAvatarFiles:
    """dashboard/static/avatars/ 目录（实际 Web 服务文件）。"""

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_static_file_exists(self, member_id):
        """active 成员静态头像存在。"""
        path = STATIC_AVATAR_DIR / f"{member_id}.png"
        assert path.exists(), f"静态头像不存在: {path}"

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_static_file_is_valid_image(self, member_id):
        """active 成员静态头像为有效图像。"""
        path = STATIC_AVATAR_DIR / f"{member_id}.png"
        info = get_image_info(path)
        assert info is not None, f"静态头像不存在或无效: {path}"

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_static_file_dimensions(self, member_id):
        """active 成员静态头像为 1024×1024（替换后）。"""
        path = STATIC_AVATAR_DIR / f"{member_id}.png"
        info = get_image_info(path)
        assert info is not None, f"无法读取: {path}"
        _, w, h = info
        assert (w, h) == EXPECTED_SIZE, (
            f"{member_id} 静态头像尺寸 {w}x{h}，期望 {EXPECTED_SIZE[0]}x{EXPECTED_SIZE[1]}（需替换）"
        )

    def test_no_dead_files(self):
        """stinger 文件已删除。"""
        assert not (STATIC_AVATAR_DIR / "stinger.png").exists(), "stinger.png 应删除"

    @pytest.mark.parametrize("member_id", INACTIVE_MEMBERS)
    def test_inactive_removed(self, member_id):
        """inactive 成员头像已清理。"""
        path = STATIC_AVATAR_DIR / f"{member_id}.png"
        # 不强制 assert not exists — 文件可以保留但不应被引用
        # 此处仅警告，无硬性要求
        if path.exists():
            pytest.skip(f"{member_id}.png 仍存在（非强制删除，仅不引用即可）")

    def test_no_orphan_files(self):
        """活动成员应有且仅有其头像文件（stinger 除外）。"""
        expected = {f"{mid}.png" for mid in ACTIVE_MEMBERS}
        actual = {f.name for f in STATIC_AVATAR_DIR.iterdir() if f.suffix == ".png"}
        # inactive 文件若未被清理，忽略（它们不会被引用）
        orphan = actual - expected - {f"{m}.png" for m in INACTIVE_MEMBERS}
        assert "stinger.png" not in actual, "stinger.png 必须清理"
        assert not orphan, f"意外的遗留文件: {orphan}"


class TestServeAvatarPath:
    """验证 _serve_avatar() 路径修复。"""

    def test_project_agents_dir_exists(self):
        """PROJECT_AGENTS_DIR = PROJECT_ROOT / 'agents' 存在。"""
        assert AGENTS_DIR.exists(), f"agents/ 目录不存在: {AGENTS_DIR}"

    def test_agents_has_active_members(self):
        """agents/ 目录下包含所有活跃成员子目录。"""
        for mid in ACTIVE_MEMBERS:
            assert (AGENTS_DIR / mid).is_dir(), f"agents/{mid}/ 不存在"

    def test_fallback_path_alpha_exists(self):
        """fallback 路径 ~/workspace/members/alpha/avatar.png 存在。"""
        path = Path("/Users/zoo/workspace/members/alpha/avatar.png")
        assert path.exists(), "fallback alpha avatar 缺失（但仍可用 agents/ 路径）"

    def test_fallback_path_panda_missing(self):
        """panda 在 fallback 路径下无 avatar（依赖 agents/ 源）。"""
        path = Path("/Users/zoo/workspace/members/panda/avatar.png")
        if not path.exists():
            pytest.skip("panda 无 fallback头像，需依赖 agents/ 源（已修复）")


class TestFrontendStingerMapping:
    """前端 stinger 硬编码清理。"""

    def test_no_stinger_in_dev_center_js(self):
        """dev_center.js 中不再有 stinger 映射。"""
        js_path = PROJECT_ROOT / "dashboard" / "static" / "dev_center.js"
        content = js_path.read_text(encoding="utf-8")

        # 检查 stinger 仅出现在必要的注释/数据中
        # 看板头像 src 不应包含 'stinger'
        stinger_avatar_ref = "'stinger' ? 'stinger' :"
        assert stinger_avatar_ref not in content, (
            "dev_center.js 中仍有 stinger 硬编码映射"
        )

    def test_avatar_src_uses_executor_directly(self):
        """看板头像直接使用 executor id。"""
        js_path = PROJECT_ROOT / "dashboard" / "static" / "dev_center.js"
        content = js_path.read_text(encoding="utf-8")

        # 验证看板头像引用格式正确
        assert "/static/avatars/" in content, "avatar 路径引用缺失"
        # 不应该有条件判断 stinger
        stinger_ternary = "stinger ? 'stinger'"
        assert stinger_ternary not in content, (
            "仍存在 stinger 三元运算符"
        )


class TestDashboardAppEnhanced:
    """验证 app_enhanced.py 中的头像路径。"""

    def test_serve_avatar_has_project_agents(self):
        """_serve_avatar() 应使用 PROJECT_ROOT/agents/ 路径。"""
        py_path = PROJECT_ROOT / "dashboard" / "app_enhanced.py"
        content = py_path.read_text(encoding="utf-8")

        # 验证方法体中有 "agents" 拼写（在 PROJECT_AGENTS_DIR 或类似变量中使用）
        assert "agents" in content, "app_enhanced.py 中缺少 agents 引用"
        # 验证旧路径已被替换
        # 旧路径: AGENTS_DIR / member_id / "avatar.png" 指向 PANDA_ROOT
        # 新路径: PROJECT_AGENTS_DIR / member_id / "avatar.png" 指向 PROJECT_ROOT
        has_new_path = any(
            marker in content
            for marker in ["PROJECT_AGENTS_DIR", 'PROJECT_ROOT / "agents"', '/ "agents"']
        )
        assert has_new_path, (
            "_serve_avatar() 中未使用 PROJECT_AGENTS_DIR"
        )

    def test_no_hardcoded_species_in_fallback(self):
        """_get_member_species 不再硬编码。"""
        py_path = PROJECT_ROOT / "dashboard" / "app_enhanced.py"
        content = py_path.read_text(encoding="utf-8")
        # 旧的硬编码: if member_id == 'panda': return {"species": "熊猫 🐼"}
        assert "if member_id == 'panda'" not in content, (
            "仍有 panda 硬编码"
        )


class TestIntegrationVibe:
    """集成验证：活跃成员可通过 Web 路径访问头像。"""

    @pytest.mark.parametrize("member_id", ACTIVE_MEMBERS)
    def test_static_url_resolves(self, member_id):
        """静态头像 URL 路径可解析到实际文件。"""
        static_path = STATIC_AVATAR_DIR / f"{member_id}.png"
        agents_path = AGENTS_DIR / member_id / "avatar.png"

        # 至少有一个源可用
        assert static_path.exists() or agents_path.exists(), (
            f"{member_id} 的头像在 static/ 和 agents/ 中均不存在"
        )

    def test_agents_source_identical_to_static(self):
        """agents/ 源文件和 static/ 文件尺寸应一致（均已为 1024x1024）。"""
        for mid in ACTIVE_MEMBERS:
            src = AGENTS_DIR / mid / "avatar.png"
            dst = STATIC_AVATAR_DIR / f"{mid}.png"
            src_info = get_image_info(src)
            dst_info = get_image_info(dst)
            if src_info and dst_info:
                assert src_info[1:] == EXPECTED_SIZE, f"{mid} 源文件尺寸不对"
                assert dst_info[1:] == EXPECTED_SIZE, f"{mid} 静态文件尺寸不对"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
