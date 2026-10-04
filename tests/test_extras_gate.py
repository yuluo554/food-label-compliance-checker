"""M5 extras 守门（plan/05 M5 DoD）：pyproject extras 必须覆盖运行期 + 测试期
import；可选依赖缺失时惰性导入报安装提示、CLI 优雅降级退出码 2。

背景（skill 阶段 6/7 实录）：FastAPI multipart 解析缺 python-multipart 时
uvicorn 启动即崩；TestClient 需要 httpx；importorskip 会把测试模块整模块静默
跳过——dev 机装过的存量包会掩盖缺声明，所以本文件静态解析 pyproject 断言包名，
不依赖"当前环境恰好装了"。
"""
import ast
import re
import sys
from pathlib import Path

import pytest

from food_label_checker.pipeline import check_text

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

# 每个 extra 必须声明的包（运行期/测试期真实 import 面）
_REQUIRED = {
    "web": {"fastapi", "uvicorn", "python-multipart"},
    "report": {"python-docx"},
    "dev": {"pytest", "httpx"},
}

# 源码/测试中出现的可选 import 名 → 发行包名
_IMPORT_TO_DIST = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "multipart": "python-multipart",
    "docx": "python-docx",
    "pytest": "pytest",
    "httpx": "httpx",
}


def _extras_declaration() -> dict:
    """从 pyproject.toml 提取 [project.optional-dependencies] 各 extra 的包名集合。"""
    block = re.search(
        r"\[project\.optional-dependencies\](.*?)(?=\n\[|\Z)", PYPROJECT, re.S
    )
    assert block, "pyproject.toml 缺 [project.optional-dependencies]"
    extras = {}
    for line in block.group(1).splitlines():
        m = re.match(r"\s*([\w-]+)\s*=\s*\[(.*)\]", line, re.S)
        if not m:
            continue
        specs = re.findall(r'"([^"]+)"', m.group(2))
        extras[m.group(1)] = {re.split(r"[><=~!]", s)[0].strip() for s in specs}
    return extras


def test_required_extras_declared():
    extras = _extras_declaration()
    for extra, pkgs in _REQUIRED.items():
        missing = pkgs - extras.get(extra, set())
        assert not missing, f"pyproject extra [{extra}] 缺声明：{missing}"


def test_extras_cover_runtime_and_test_imports():
    """src/ 与 tests/ 中出现的全部可选依赖 import，必须被某个 extra 声明。"""
    extras = _extras_declaration()
    declared = set().union(*extras.values())
    imported = set()
    for root in (REPO_ROOT / "src" / "food_label_checker", REPO_ROOT / "tests"):
        for py in root.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    imported.add(node.module.split(".")[0])
    optional = sorted(i for i in imported if i in _IMPORT_TO_DIST)
    for imp in optional:
        dist = _IMPORT_TO_DIST[imp]
        assert dist in declared, (
            f"import {imp}（发行名 {dist}）未入任何 extra——干净环境将静默缺依赖"
            "或启动即崩（extras 第三形态教训）"
        )


# ---------------------------------------------------------------------------
# 缺依赖优雅降级（mock 注入模拟缺依赖路径，不真卸载）
# ---------------------------------------------------------------------------

def test_webapp_missing_dependency_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from food_label_checker import webapp

    with pytest.raises(ImportError) as ei:
        webapp.create_app()
    assert "[web]" in str(ei.value)


def test_report_missing_dependency_hint(monkeypatch, sample_text, tmp_path):
    monkeypatch.setitem(sys.modules, "docx", None)
    from food_label_checker.report.docx_report import generate_report

    result = check_text(sample_text, ["gb7718-2011"])
    with pytest.raises(ImportError) as ei:
        generate_report(result, tmp_path / "x.docx")
    assert "[report]" in str(ei.value)


def test_cli_report_missing_dependency_exit_2(
    monkeypatch, sample_text, tmp_path, capsys
):
    """CLI --report 在缺 report 扩展时优雅降级：退出码 2 + 安装提示，不崩溃。"""
    monkeypatch.setitem(sys.modules, "docx", None)
    from food_label_checker.cli import main

    target = tmp_path / "l.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["check", str(target), "--report", str(tmp_path / "o.docx")]) == 2
    assert "report" in capsys.readouterr().err


def test_cli_web_missing_dependency_exit_2(monkeypatch, capsys):
    """flcheck web 在缺 web 扩展时优雅降级：退出码 2 + 安装提示。"""
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from food_label_checker.cli import main

    assert main(["web"]) == 2
    assert "[web]" in capsys.readouterr().err
