"""README 自述测试数守门（坑 #10）：README 里写的「N 项」必须等于实际收集数。

本仓没有这个守门时，新增测试后 README 的数字全靠人工同步；二次迭代前的历史
里已经发生过漂移（诊断报告里记录「plan 6 处写 429 而实测 431」这类问题在
兄弟仓出现过，本仓则出现过 191 与实际收集数不一致的窗口）。

判据只认一个位置：README「特性」段的 `全离线 pytest（N 项`。这是读者第一眼
看到的数字，也是最容易过期的那处。
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

# README「特性」段里自述测试数的句式（只匹配这一处，避免误伤历史记录里的旧数字）
_PATTERN = re.compile(r"全离线 pytest（(\d+) 项")


def _readme_claimed_count():
    with open(README, encoding="utf-8") as fh:
        text = fh.read()
    hits = _PATTERN.findall(text)
    assert hits, "README 里找不到「全离线 pytest（N 项」句式——守门失去锚点，需先修 README"
    assert len(hits) == 1, f"README 里「全离线 pytest（N 项」出现 {len(hits)} 次，应只出现 1 次：{hits}"
    return int(hits[0])


def test_readme_test_count_matches_collection():
    """README 自述的测试数必须等于 pytest 实际收集数。"""
    claimed = _readme_claimed_count()
    # 收集数只能在 session 维度拿到；这里用 `--collect-only` 子进程（只收集不执行，
    # 不会递归跑到本用例）。用 sys.executable 而非 `pytest`，避免 PATH 上的解释器
    # 与本环境不一致导致假红。
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, f"收集失败：\n{proc.stdout}\n{proc.stderr}"
    m = re.search(r"(\d+) tests collected", proc.stdout) or re.search(
        r"(\d+) tests collected", proc.stderr
    )
    assert m, f"无法从 pytest --collect-only 输出里解析收集数：\n{proc.stdout[-800:]}"
    actual = int(m.group(1))
    assert actual == claimed, (
        f"README 自述 {claimed} 项，实际收集 {actual} 项——新增/删除测试后必须同步 README"
    )
