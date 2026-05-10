"""Harness 元规则验证器测试。

覆盖 5 个验证函数，每个函数至少 3 个测试用例：
- validate_delivery: 五件套交接
- parse_review_grade: P1/P2/P3 分级审核
- check_release_signal: 代码合入放行信号
- check_tdd_compliance: TDD 开发铁则
- check_message_route: 跨成员交互铁则
"""

import os
import tempfile

import pytest

from framework.core.harness.validators import (
    DeliveryPackage,
    MESSAGE_LENGTH_THRESHOLD,
    RELEASE_SIGNALS,
    ReviewGrade,
    check_message_route,
    check_release_signal,
    check_tdd_compliance,
    parse_review_grade,
    validate_delivery,
)


class TestValidateDelivery:
    """元规则 #1：五件套交接校验。"""

    def test_complete_package_passes(self):
        pkg = DeliveryPackage(
            task_id="3.2.2",
            commit_hash="abc123",
            test_results="all passed",
            review_record="LGTM",
            change_summary="implement validators",
        )
        assert validate_delivery(pkg) == []

    def test_missing_task_id(self):
        pkg = DeliveryPackage(
            task_id="",
            commit_hash="abc123",
            test_results="ok",
            review_record="LGTM",
            change_summary="x",
        )
        errors = validate_delivery(pkg)
        assert "缺少 task_id" in errors

    def test_missing_commit_hash(self):
        pkg = DeliveryPackage(
            task_id="3.2.2",
            commit_hash="",
            test_results="ok",
            review_record="LGTM",
            change_summary="x",
        )
        errors = validate_delivery(pkg)
        assert "缺少 commit_hash" in errors

    def test_all_missing_yields_five_errors(self):
        pkg = DeliveryPackage(
            task_id="",
            commit_hash="",
            test_results="",
            review_record="",
            change_summary="",
        )
        errors = validate_delivery(pkg)
        assert len(errors) == 5
        assert "缺少 task_id" in errors
        assert "缺少 commit_hash" in errors
        assert "缺少 test_results" in errors
        assert "缺少 review_record" in errors
        assert "缺少 change_summary" in errors


class TestParseReviewGrade:
    """元规则 #2：P1/P2/P3 分级审核解析。"""

    def test_p1_grade(self):
        assert parse_review_grade({"grade": "P1"}) == ReviewGrade.P1

    def test_p2_grade(self):
        assert parse_review_grade({"grade": "P2"}) == ReviewGrade.P2

    def test_p3_grade(self):
        assert parse_review_grade({"grade": "P3"}) == ReviewGrade.P3

    def test_missing_grade_returns_none(self):
        assert parse_review_grade({}) is None

    def test_invalid_grade_returns_none(self):
        assert parse_review_grade({"grade": "P4"}) is None

    def test_non_dict_returns_none(self):
        assert parse_review_grade("not a dict") is None  # type: ignore[arg-type]

    def test_empty_grade_returns_none(self):
        assert parse_review_grade({"grade": ""}) is None


class TestCheckReleaseSignal:
    """元规则 #4：代码合入放行信号检查。"""

    def test_lgtm_uppercase_passes(self):
        assert check_release_signal("LGTM") is True

    def test_lgtm_lowercase_passes(self):
        assert check_release_signal("lgtm") is True

    def test_lgtm_with_whitespace_passes(self):
        assert check_release_signal("  LGTM  ") is True

    def test_chinese_pass_signal(self):
        assert check_release_signal("通过") is True

    def test_chinese_can_merge_signal(self):
        assert check_release_signal("可以合入") is True

    def test_empty_string_blocks(self):
        assert check_release_signal("") is False

    def test_conditional_pass_blocks(self):
        # Duci 说的"条件性通过"不算放行
        assert check_release_signal("条件性通过") is False

    def test_unrelated_text_blocks(self):
        assert check_release_signal("looks good but...") is False

    def test_release_signals_set_intact(self):
        # 防止有人误改放行关键词集合
        assert RELEASE_SIGNALS == {"lgtm", "通过", "可以合入"}


class TestCheckTddCompliance:
    """元规则 #9：TDD 开发铁则。"""

    def test_test_before_source_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "test_x.py")
            src_path = os.path.join(tmp, "x.py")
            with open(test_path, "w") as f:
                f.write("# test")
            with open(src_path, "w") as f:
                f.write("# src")
            # 显式设置 mtime: test 早于 source
            os.utime(test_path, (1000, 1000))
            os.utime(src_path, (2000, 2000))
            assert check_tdd_compliance(test_path, src_path) == []

    def test_source_before_test_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "test_x.py")
            src_path = os.path.join(tmp, "x.py")
            with open(src_path, "w") as f:
                f.write("# src")
            with open(test_path, "w") as f:
                f.write("# test")
            os.utime(src_path, (1000, 1000))
            os.utime(test_path, (2000, 2000))
            errors = check_tdd_compliance(test_path, src_path)
            assert len(errors) == 1
            assert "TDD 违规" in errors[0]

    def test_same_mtime_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "test_x.py")
            src_path = os.path.join(tmp, "x.py")
            with open(test_path, "w") as f:
                f.write("# test")
            with open(src_path, "w") as f:
                f.write("# src")
            os.utime(test_path, (1500, 1500))
            os.utime(src_path, (1500, 1500))
            errors = check_tdd_compliance(test_path, src_path)
            assert len(errors) == 1
            assert "TDD 违规" in errors[0]

    def test_missing_test_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "missing_test.py")
            src_path = os.path.join(tmp, "x.py")
            with open(src_path, "w") as f:
                f.write("# src")
            errors = check_tdd_compliance(test_path, src_path)
            assert len(errors) == 1
            assert "测试文件" in errors[0] and "不存在" in errors[0]

    def test_missing_source_file_returns_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "test_x.py")
            src_path = os.path.join(tmp, "missing_src.py")
            with open(test_path, "w") as f:
                f.write("# test")
            errors = check_tdd_compliance(test_path, src_path)
            assert len(errors) == 1
            assert "源文件" in errors[0]


class TestCheckMessageRoute:
    """元规则 #13：跨成员交互铁则。"""

    def test_short_message_passes(self):
        assert check_message_route("hi", use_shared=False) is None

    def test_short_message_via_shared_passes(self):
        assert check_message_route("hi", use_shared=True) is None

    def test_long_message_via_shared_passes(self):
        long = "x" * (MESSAGE_LENGTH_THRESHOLD + 1)
        assert check_message_route(long, use_shared=True) is None

    def test_long_message_not_via_shared_fails(self):
        long = "x" * (MESSAGE_LENGTH_THRESHOLD + 1)
        result = check_message_route(long, use_shared=False)
        assert result is not None
        assert str(MESSAGE_LENGTH_THRESHOLD) in result
        assert "shared/" in result

    def test_at_threshold_passes(self):
        # 边界：恰好等于阈值不触发
        msg = "x" * MESSAGE_LENGTH_THRESHOLD
        assert check_message_route(msg, use_shared=False) is None

    def test_empty_message_passes(self):
        assert check_message_route("", use_shared=False) is None
