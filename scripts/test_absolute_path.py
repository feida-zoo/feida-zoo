#!/usr/bin/env python3
"""
测试绝对路径安全问题
"""

from pathlib import Path

# 测试路径拼接行为
base_path = Path("/tmp/test").resolve()
test_cases = [
    "normal",
    "../evil",
    "/etc/passwd",  # 绝对路径
    "normal/../evil",
]

print("测试路径拼接行为:")
for member_id in test_cases:
    result = base_path / member_id
    print(f"  base: {base_path}")
    print(f"  id:   '{member_id}'")
    print(f"  result: {result}")
    print(f"  is_absolute: {result.is_absolute()}")
    print(f"  relative_to base: ", end="")
    try:
        rel = result.relative_to(base_path)
        print(f"✅ {rel}")
    except ValueError:
        print(f"❌ 路径逃逸!")
    print()


# 测试Path.resolve()的行为
print("\n测试Path.resolve()行为:")
test_paths = [
    "/tmp/test/../etc/passwd",
    "/tmp/test/./../evil",
    "/tmp/test/normal/../../etc",
]

for path_str in test_paths:
    p = Path(path_str)
    resolved = p.resolve()
    print(f"  '{path_str}' -> {resolved}")
    print(f"    规范化后: {p}")