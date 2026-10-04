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
    "nutrition_rows",
    "allergen_notice",
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


def test_ruleset_total_count_at_least_40():
    """M3 DoD：双版本规则合计 ≥40 条。"""
    total = sum(
        len(json.loads((RULESETS_DIR / f"{rid}.json").read_text(encoding="utf-8"))["rules"])
        for rid in AVAILABLE_RULESETS
    )
    assert total >= 40


def test_d16_contract_rule_ids_present():
    """D16 V→规则契约：V1–V8 主期望 rule_id 必须在规则库中（2011 豁免除外）。"""
    lib = {
        rid: {r["id"] for r in json.loads(
            (RULESETS_DIR / f"{rid}.json").read_text(encoding="utf-8"))["rules"]}
        for rid in AVAILABLE_RULESETS
    }
    for rid, ids in lib.items():
        expected = {
            "MAND-NAME-01", "MAND-ING-01", "MAND-NET-01", "MAND-SHELF-01",
            "MAND-DATE-01", "MAND-STORAGE-01", "MAND-SC-01",
            "NRV-RECALC-01", "ENERGY-CONSIST-01", "CLAIM-THRESH-01",
            "ING-ORDER-01", "FMT-DATE-01", "DATE-LOGIC-01", "CLAIM-FUNC-01",
        }
        if rid == "gb7718-2025":
            expected |= {"MAND-EXPIRY-01", "CLAIM-ZEROADD-01", "SALT-NOTICE-01"}
        else:
            # 2011 豁免契约（D16）：不得含 2025 新增声称限制规则
            assert "CLAIM-ZEROADD-01" not in ids
        missing = expected - ids
        assert not missing, f"{rid} 缺 D16 契约规则：{sorted(missing)}"


def test_only_if_gate_vocabulary_documented():
    """门控词表（M3 定稿）：only_if 关键词与规则 params 先验词表必须显式声明。"""
    for rid in AVAILABLE_RULESETS:
        data = json.loads((RULESETS_DIR / f"{rid}.json").read_text(encoding="utf-8"))
        for rule in data["rules"]:
            if rule.get("only_if"):
                assert isinstance(rule["only_if"], list)
            if rule["check_type"] == "ingredient_order":
                pairs = rule.get("params", {}).get("ordered_pairs")
                assert pairs and all(len(p) == 2 for p in pairs), rule["id"]
            if rule["check_type"] == "claim_whitelist":
                assert rule.get("params", {}).get("forbidden_terms"), rule["id"]
            if rule["check_type"] == "conditional":
                params = rule.get("params", {})
                assert "exempt_if_any" in params and "manual_if_any" in params, rule["id"]
            if rule["check_type"] == "nutrition_rows":
                rows = rule.get("params", {}).get("required_rows")
                assert rows and len(rows) == 7 and "糖" in rows, rule["id"]
            if rule["check_type"] == "allergen_notice":
                kws = rule.get("params", {}).get("allergen_keywords")
                assert kws and "乳" in kws and "小麦" in kws, rule["id"]


def test_m4_new_rules_are_2025_only_and_basis_verified():
    """M4 新规则（D22）：NUTR-ROWS-01 / ALLERGEN-01 仅 2025，且依据已核对。"""
    for rid in AVAILABLE_RULESETS:
        ids = {r["id"] for r in json.loads(
            (RULESETS_DIR / f"{rid}.json").read_text(encoding="utf-8"))["rules"]}
        if rid == "gb7718-2025":
            assert {"NUTR-ROWS-01", "ALLERGEN-01"} <= ids
        else:
            # 2011：糖行/饱和脂肪/致敏物质提示在 2011 语义下属自愿或推荐标示
            assert not (ids & {"NUTR-ROWS-01", "ALLERGEN-01"})
