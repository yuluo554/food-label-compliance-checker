"""规则集 JSON 结构守门测试（"无出处不落库"纪律的第一道闸）。

每条规则必须：id 唯一、check_type 已知或显式规划、basis.standard 以 GB 开头、
basis.status 只允许"已核对/待核对"两值；规则集 id 与文件名一致。
"""
import json
from pathlib import Path

import pytest

from food_label_checker.rules.engine import AVAILABLE_RULESETS, RULESETS_DIR

KNOWN_CHECK_TYPES = {
    "mandatory_field",
    "format",
    "nrv_recalc",
    "energy_consistency",
    "ingredient_order",
    "claim_threshold",
    "claim_whitelist",
    "date_logic",
    "conditional",
}
LEGAL_BASIS_STATUS = {"已核对", "待核对"}


@pytest.mark.parametrize("ruleset_id", AVAILABLE_RULESETS)
def test_ruleset_schema(ruleset_id):
    data = json.loads((RULESETS_DIR / f"{ruleset_id}.json").read_text(encoding="utf-8"))
    assert data["ruleset_id"] == ruleset_id
    assert data["title"]
    ids = [rule["id"] for rule in data["rules"]]
    assert len(ids) == len(set(ids)), "规则 id 必须唯一"

    for rule in data["rules"]:
        assert rule["name"], f"{rule['id']} 缺少 name"
        assert rule["check_type"] in KNOWN_CHECK_TYPES, f"{rule['id']} check_type 非法"
        basis = rule.get("basis", {})
        assert basis.get("standard", "").startswith("GB"), f"{rule['id']} 缺标准号"
        assert basis.get("status") in LEGAL_BASIS_STATUS, f"{rule['id']} basis.status 非法"
        assert rule.get("advice"), f"{rule['id']} 缺整改建议"


def test_rulesets_dir_matches_available():
    on_disk = sorted(p.stem for p in RULESETS_DIR.glob("*.json"))
    assert on_disk == sorted(AVAILABLE_RULESETS)
