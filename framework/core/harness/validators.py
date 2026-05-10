"""
Harness 元规则验证器
将 SKILL.md 自然语言规则转为可执行代码断言

迁移矩阵（来自 v1.1 §2.8）：
- 元规则 #1  五件套交接       → validate_delivery()
- 元规则 #2  P1/P2/P3 分级审核 → parse_review_grade()
- 元规则 #4  代码合入放行信号  → check_release_signal()
- 元规则 #9  TDD 开发铁则      → check_tdd_compliance()
- 元规则 #13 跨成员交互铁则    → check_message_route()
"""

import os
import stat
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewGrade(Enum):
    """审核评分等级。"""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


@dataclass
class DeliveryPackage:
    """五件套交付件。

    元规则 #1：交付时必须包含以下五个要素，缺一不可。
    """

    task_id: str
    commit_hash: str
    test_results: str
    review_record: str
    change_summary: str


def validate_delivery(pkg: DeliveryPackage) -> List[str]:
    """元规则 #1：五件套交接校验。

    Args:
        pkg: 待校验的交付件

    Returns:
        错误列表，空列表表示校验通过
    """
    errors: List[str] = []
    if not pkg.task_id:
        errors.append("缺少 task_id")
    if not pkg.commit_hash:
        errors.append("缺少 commit_hash")
    if not pkg.test_results:
        errors.append("缺少 test_results")
    if not pkg.review_record:
        errors.append("缺少 review_record")
    if not pkg.change_summary:
        errors.append("缺少 change_summary")
    return errors


def parse_review_grade(review_record: Dict[str, Any]) -> Optional[ReviewGrade]:
    """元规则 #2：P1/P2/P3 分级审核评分解析。

    Args:
        review_record: 审核记录字典，期望包含 "grade" 键

    Returns:
        合规返回 ReviewGrade，不合规返回 None
    """
    if not isinstance(review_record, dict):
        return None
    grade = review_record.get("grade")
    if not grade:
        return None
    try:
        return ReviewGrade(grade)
    except ValueError:
        return None


# 放行信号关键词（精确匹配，大小写不敏感）
RELEASE_SIGNALS = {"lgtm", "通过", "可以合入"}


def check_release_signal(review_text: str) -> bool:
    """元规则 #4：代码合入放行信号检查。

    必须出现明确放行关键词之一（LGTM / 通过 / 可以合入），
    且不能包含「条件性通过」，无放行语 → 不放行。

    Args:
        review_text: 审核结论文本

    Returns:
        True 表示放行，False 表示未放行
    """
    if not review_text:
        return False
    normalized = review_text.lower().strip()
    if "条件性通过" in normalized:
        return False
    return any(signal in normalized for signal in RELEASE_SIGNALS)


def check_tdd_compliance(test_file: str, source_file: str) -> List[str]:
    """元规则 #9：TDD 开发铁则。

    测试文件必须先于源文件创建（测试文件 mtime <= 源文件 mtime）。
    未遵循 → 阻塞开发。

    Args:
        test_file: 测试文件绝对路径
        source_file: 源文件绝对路径

    Returns:
        错误列表，空列表表示校验通过
    """
    errors: List[str] = []

    if not os.path.exists(test_file):
        errors.append(f"TDD 违规：测试文件 {test_file} 不存在")
        return errors

    if not os.path.exists(source_file):
        errors.append(f"源文件 {source_file} 不存在（可能尚未创建）")
        return errors

    test_mtime = os.stat(test_file)[stat.ST_MTIME]
    source_mtime = os.stat(source_file)[stat.ST_MTIME]

    if source_mtime <= test_mtime:
        errors.append(
            f"TDD 违规：源文件 mtime({source_mtime}) <= 测试文件 mtime({test_mtime})，"
            f"测试必须先于实现"
        )
    return errors


# 跨成员消息字数阈值
MESSAGE_LENGTH_THRESHOLD = 200


def check_message_route(long_message: str, use_shared: bool) -> Optional[str]:
    """元规则 #13：跨成员交互铁则。

    消息长度 > 200 字必须走 shared/ 目录，
    否则 → 错误。

    Args:
        long_message: 待发送的消息内容
        use_shared: 是否使用 shared/ 目录传递

    Returns:
        错误信息字符串，None 表示校验通过
    """
    if long_message and len(long_message) > MESSAGE_LENGTH_THRESHOLD and not use_shared:
        return (
            f"消息长度 {len(long_message)} > {MESSAGE_LENGTH_THRESHOLD}，"
            f"必须写入 shared/ 目录"
        )
    return None
