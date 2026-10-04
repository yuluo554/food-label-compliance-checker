"""双标尺规则引擎测试：强制标示核查、双标尺对照、类目门控、依据纪律。"""
from food_label_checker.models import LEVEL_FAIL, LEVEL_PASS
from food_label_checker.parser import parse_label
from food_label_checker.rules.engine import (
    dual_diff,
    gate_matches,
    load_ruleset,
    run_ruleset,
)


def _fails(result):
    return {f.rule_id for f in result.findings if f.level == LEVEL_FAIL}


def test_dual_ruler_on_sample(sample_text):
    card = parse_label(sample_text)

    r2011 = run_ruleset(card, load_ruleset("gb7718-2011"))
    r2025 = run_ruleset(card, load_ruleset("gb7718-2025"))

    # 样例缺净含量 → 两把标尺都报；缺保质期到期日 → 仅 2025 报
    assert _fails(r2011) == {"MAND-NET-01"}
    assert _fails(r2025) == {"MAND-NET-01", "MAND-EXPIRY-01"}

    diff = dual_diff({"gb7718-2011": r2011, "gb7718-2025": r2025},
                     "gb7718-2011", "gb7718-2025")
    assert diff["new_fails"] == ["MAND-EXPIRY-01"]
    assert diff["resolved_fails"] == []


def test_pass_findings_recorded_and_stats_consistent(sample_text):
    card = parse_label(sample_text)
    result = run_ruleset(card, load_ruleset("gb7718-2011"))
    levels = [f.level for f in result.findings]
    assert LEVEL_PASS in levels  # 食品名称已标示 → 有合规结论
    stats = result.stats
    assert stats["pass"] + stats["fail"] + stats["manual"] == stats["checked"]
    assert stats["checked"] == len(result.findings)


def test_every_finding_carries_basis_and_pending_flag(sample_text):
    """无出处纪律：骨架期全部规则 status=待核对 → 结论必须带待核对标记。"""
    card = parse_label(sample_text)
    for rid in ("gb7718-2011", "gb7718-2025"):
        for finding in run_ruleset(card, load_ruleset(rid)).findings:
            assert finding.basis.get("standard", "").startswith("GB")
            assert finding.basis.get("status") == "待核对"
            assert finding.flagged_pending_basis is True


def test_only_if_gate_blocks_other_category():
    """类目隔离门控：不命中关键词的类目不得执行该规则（含 mandatory 类型）。"""
    rule = {
        "id": "G-TEST-01",
        "name": "酱油专属检查",
        "check_type": "mandatory_field",
        "param": "nutrition_table",
        "basis": {"standard": "GB/T 18186", "clause": "待核对", "status": "待核对"},
        "only_if": ["酱油"],
    }
    soy_card = parse_label("食品名称：酿造酱油\n配料：水、大豆、小麦、食盐")
    milk_card = parse_label("食品名称：牧云 灭菌乳\n配料：生牛乳")

    assert gate_matches(rule["only_if"], soy_card) is True
    assert gate_matches(rule["only_if"], milk_card) is False

    soy_result = run_ruleset(soy_card, {"ruleset_id": "test", "rules": [rule]})
    milk_result = run_ruleset(milk_card, {"ruleset_id": "test", "rules": [rule]})
    assert soy_result.stats["checked"] == 1
    assert milk_result.stats["checked"] == 0
    assert milk_result.stats["skipped"] == 1


def test_unknown_check_type_goes_manual_not_crash():
    rule = {
        "id": "FUTURE-01",
        "name": "未来检查类型",
        "check_type": "nrv_recalc",
        "param": "nutrition_table",
        "basis": {"standard": "GB 28050-2011", "clause": "待核对", "status": "待核对"},
        "only_if": None,
    }
    card = parse_label("食品名称：测试乳")
    result = run_ruleset(card, {"ruleset_id": "test", "rules": [rule]})
    assert result.stats["manual"] == 1
    assert "尚未实现" in result.findings[0].message
