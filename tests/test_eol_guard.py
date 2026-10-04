"""EOL 守门（决策 D13）：冻结 fixtures 与知识文件必须纯 LF，.gitattributes 门禁在位。

`.gitattributes` 的 `* text=auto eol=lf` 保证 checkout 后工作区为 LF；本测试在
字节层面守门，防止 CRLF 混入破坏位级复现（manifest sha256 对行尾敏感）。
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "data" / "generated" / "frozen"


def test_gitattributes_eol_gate_in_place():
    attrs = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "eol=lf" in attrs, ".gitattributes 缺少 eol=lf 门禁（决策 D13）"


def test_frozen_fixtures_have_no_cr_bytes():
    assert FROZEN_DIR.exists(), "冻结 fixtures 缺失"
    for path in sorted(FROZEN_DIR.rglob("*")):
        if path.is_file():
            assert b"\r" not in path.read_bytes(), f"发现 CR 字节（CRLF 污染）：{path.name}"


def test_nutrient_reference_no_cr():
    ref = REPO_ROOT / "src" / "food_label_checker" / "rules" / "nutrient_reference.json"
    assert b"\r" not in ref.read_bytes()
