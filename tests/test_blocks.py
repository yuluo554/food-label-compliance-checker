"""条文块守门测试（M3）：四部标准块文件齐全、块号唯一、关键数值条款挂原文。

匹配口径：PDF 提取文本偶有小数拆行（如 "0."/"5g"），一律用「去全部空白」
方式在 title+text 拼接中匹配。
"""
import json
import re
from pathlib import Path

import pytest

from food_label_checker.rules.engine import AVAILABLE_RULESETS, RULESETS_DIR

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOCKS_DIR = REPO_ROOT / "data" / "knowledge" / "blocks"

STANDARD_FILES = (
    "gb7718-2011", "gb7718-2025", "gb28050-2011", "gb28050-2025",
)

# 关键数值/用语条款 → 必须命中的原文片段（去空白匹配）
GROUNDING = {
    "gb28050-2011": {
        "A.1": ["8400kJ", "蛋白质", "60g", "2000mg"],
        "A.2": ["修约间隔为1"],
        "6.4": ["120%标示值"],
        "C.1": ["无或不含糖", "0.5g/100g", "低糖", "5g/100g", "低钠", "120mg/100g"],
        "4.1": ["核心营养素"],
    },
    "gb28050-2025": {
        "2.3": ["蛋白质17、脂肪37、碳水化合物17"],
        "4.1": ["饱和脂肪", "糖和钠"],
        "4.5": ["儿童青少年应避免过量摄入盐油糖"],
        "6.7": ["120%标示值"],
        "A.1": ["8400kJ"],
        "A.3.2": ["修约间隔为1"],
        "C.1": ["无或不含糖", "0.5g/100g"],
    },
    "gb7718-2011": {
        "4.1.3.1.2": ["递减顺序", "2%"],
        "4.1.7.3": ["年、月、日"],
        "C.3": ["2位数字"],
        "3.6": ["预防、治疗疾病"],
        "4.3.1": ["食醋", "味精"],
        "4.1.6.2": ["联系方式"],
        "4.1.10": ["标准代号和顺序号"],
    },
    "gb7718-2025": {
        "4.1": ["营养标签", "保质期到期日", "致敏物质提示"],
        "4.3.2": ["递减顺序", "2%"],
        "4.4.2.2": ["不添加", "不使用"],
        "A.5.3": ["零添加", "无添加", "未添加"],
        "4.7.1": ["年、月、日", "保质期到期日"],
        "10.1": ["食醋", "食用盐", "味精", "葡萄酒"],
        "3.5": ["预防、治疗疾病"],
        "A.2.1": ["2010年03月20日", "20100320"],
    },
}


@pytest.mark.parametrize("file_id", STANDARD_FILES)
def test_blocks_file_structure(file_id):
    doc = json.loads((BLOCKS_DIR / f"{file_id}.json").read_text(encoding="utf-8"))
    assert doc["file_id"] == file_id
    assert doc["standard"].startswith("GB")
    assert doc["source_pdf"].startswith("data/knowledge/raw/")
    assert re.fullmatch(r"[0-9a-f]{64}", doc["source_pdf_sha256"])
    assert (REPO_ROOT / doc["source_pdf"]).exists()
    assert doc["block_count"] == len(doc["blocks"])
    ids = [b["block_id"] for b in doc["blocks"]]
    assert len(ids) == len(set(ids)), "块号必须唯一"
    for b in doc["blocks"]:
        assert b["clause"] == b["block_id"]
        assert isinstance(b["text"], str) and b["page"] >= 1


@pytest.mark.parametrize("file_id", sorted(GROUNDING))
def test_key_clauses_grounded(file_id):
    """关键数值条款按去空白口径挂原文（NRV/系数/阈值/误差/提示语/同义语）。"""
    doc = json.loads((BLOCKS_DIR / f"{file_id}.json").read_text(encoding="utf-8"))
    blocks = {b["block_id"]: b for b in doc["blocks"]}
    for clause, needles in GROUNDING[file_id].items():
        assert clause in blocks, f"{file_id} 缺块 {clause}"
        hay = "".join((blocks[clause]["title"] + blocks[clause]["text"]).split())
        for needle in needles:
            assert "".join(needle.split()) in hay, f"{file_id}#{clause} 缺『{needle}』"


def test_source_pdf_sha256_matches():
    """块文件登记的 PDF sha256 与 raw/ 实际文件一致（挂原文出处完整性）。"""
    import hashlib
    for file_id in STANDARD_FILES:
        doc = json.loads((BLOCKS_DIR / f"{file_id}.json").read_text(encoding="utf-8"))
        raw = (REPO_ROOT / doc["source_pdf"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == doc["source_pdf_sha256"]


@pytest.mark.parametrize("ruleset_id", AVAILABLE_RULESETS)
def test_ruleset_quote_refs_resolve(ruleset_id):
    """规则集每条规则的 basis.quote_ref 必须能解析到条文块（无出处不落库）。"""
    data = json.loads(
        (RULESETS_DIR / f"{ruleset_id}.json").read_text(encoding="utf-8")
    )
    cache = {}
    for rule in data["rules"]:
        basis = rule["basis"]
        ref = basis.get("quote_ref")
        assert ref and "#" in ref, f"{rule['id']} 缺 quote_ref"
        file_id, clause = ref.split("#", 1)
        if file_id not in cache:
            cache[file_id] = {
                b["block_id"]: b for b in
                json.loads((BLOCKS_DIR / file_id).read_text(encoding="utf-8"))["blocks"]
            }
        assert clause in cache[file_id], f"{rule['id']} quote_ref 指向不存在的块：{ref}"
        # status=已核对 的规则，其 clause 不得再标"待核对"
        if basis.get("status") == "已核对":
            assert "待核对" not in basis.get("clause", "")
