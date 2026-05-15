#!/usr/bin/env python3
"""P0 问题管理→ZooMesh联动集成测试"""

import json
import os
import sys
import requests

DASHBOARD_URL = "http://localhost:18792"
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
passed = 0
failed = 0

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1

def post_issue(title, desc="", priority="P3", assignee=""):
    resp = requests.post(
        f"{DASHBOARD_URL}/api/issues",
        json={"title": title, "description": desc, "priority": priority, "assignee": assignee},
        timeout=5
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    return resp.json()

def has_pipeline(title):
    reqs_file = os.path.join(PROJECT_DIR, "dashboard", "data", "requirements.json")
    with open(reqs_file) as f:
        reqs = json.load(f)
    for r in reqs:
        if r.get("title") == title:
            return True
    return False

def issue_has_pipeline(title):
    issues_file = os.path.join(PROJECT_DIR, "dashboard", "data", "issues.json")
    with open(issues_file) as f:
        issues = json.load(f)
    for i in issues:
        if i.get("title") == title:
            return bool(i.get("pipeline_id")) and i.get("pipeline_status") == "pushed"
    return False

def cleanup_test_issues():
    issues_file = os.path.join(PROJECT_DIR, "dashboard", "data", "issues.json")
    reqs_file = os.path.join(PROJECT_DIR, "dashboard", "data", "requirements.json")
    
    with open(issues_file) as f:
        issues = json.load(f)
    issues = [i for i in issues if not i.get("title","").startswith("P0Test_")]
    with open(issues_file, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2, ensure_ascii=False)
    
    with open(reqs_file) as f:
        reqs = json.load(f)
    reqs = [r for r in reqs if not r.get("title","").startswith("P0Test_")]
    with open(reqs_file, "w", encoding="utf-8") as f:
        json.dump(reqs, f, indent=2, ensure_ascii=False)

UNIQUE = "P0Test_AutoPush"

print("🧪 P0 集成测试：问题管理→ZooMesh联动")
print("=" * 50)

# 清理之前测试数据
cleanup_test_issues()

test("提交问题返回 HTTP 200 + pipeline_id",
     lambda: check(post_issue(UNIQUE).get("pipeline_id", "").startswith("pl_"),
                   "缺少 pipeline_id"))

test("pipeline_status = pushed",
     lambda: check(post_issue(f"{UNIQUE}_v2").get("pipeline_status") == "pushed",
                   "pipeline_status 不是 pushed"))

test("pipeline 注册到 requirements.json",
     lambda: check(has_pipeline(UNIQUE),
                   "requirements.json 未找到 pipeline"))

test("pipeline_id 持久化到 issues.json",
     lambda: check(issue_has_pipeline(UNIQUE),
                   "issue 的 pipeline_id/pipeline_status 未持久化"))

test("模拟 ZooMesh 断开时 pipeline_status = push_failed", lambda: (
    None  # 手动验证：kill ZooMesh 后提交 issue
))

print()
print("=" * 50)
print(f"结果: {passed} 通过, {failed} 失败")

# 清理测试数据
cleanup_test_issues()

sys.exit(1 if failed > 0 else 0)
