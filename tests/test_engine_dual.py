"""双标尺规则引擎测试：强制标示核查、双标尺对照、类目门控、依据纪律。"""
from food_label_checker.models import LEVEL_FAIL, LEVEL_MANUAL, LEVEL_PASS
from food_label_checker.parser import parse_label
from food_label_checker.rules.engine import (
    AVAILABLE_RULESETS,
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

    # 样例缺净含量、营养成分表（GB 28050 两版均强制）→ 两把标尺都报；
    # 缺保质期到期日与盐油糖提示语 → 仅 2025 报（新版要求）
    assert _fails(r2011) == {"MAND-NET-01", "NUTR-TABLE-01"}
    assert _fails(r2025) == {
        "MAND-NET-01",
        "MAND-EXPIRY-01",
        "NUTR-TABLE-01",
        "SALT-NOTICE-01",
    }

    diff = dual_diff({"gb7718-2011": r2011, "gb7718-2025": r2025},
                     "gb7718-2011", "gb7718-2025")
    assert diff["new_fails"] == ["MAND-EXPIRY-01", "SALT-NOTICE-01"]
    assert diff["resolved_fails"] == []


def test_pass_findings_recorded_and_stats_consistent(sample_text):
    card = parse_label(sample_text)
    for rid in AVAILABLE_RULESETS:
        ruleset = load_ruleset(rid)
        result = run_ruleset(card, ruleset)
        levels = [f.level for f in result.findings]
        assert LEVEL_PASS in levels  # 食品名称已标示 → 有合规结论
        stats = result.stats
        # 结论条数口径：行级结论可多于规则数，但必等于三级之和
        assert stats["pass"] + stats["fail"] + stats["manual"] == len(result.findings)
        # 规则数口径：checked + skipped(门控) + not_run(前置缺失) == 全部规则
        assert stats["checked"] + stats["skipped"] + stats["not_run"] == len(ruleset["rules"])


def test_every_finding_carries_basis_and_pending_flag(sample_text):
    """依据纪律：flagged_pending_basis 必须等于 basis.status != 已核对。"""
    card = parse_label(sample_text)
    for rid in AVAILABLE_RULESETS:
        for finding in run_ruleset(card, load_ruleset(rid)).findings:
            assert finding.basis.get("standard", "").startswith("GB")
            status = finding.basis.get("status")
            assert status in ("已核对", "待核对")
            assert finding.flagged_pending_basis is (status != "已核对")


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
        "check_type": "future_type_xx",
        "param": "nutrition_table",
        "basis": {"standard": "GB 28050-2011", "clause": "待核对", "status": "待核对"},
        "only_if": None,
    }
    card = parse_label("食品名称：测试乳")
    result = run_ruleset(card, {"ruleset_id": "test", "rules": [rule]})
    assert result.stats["manual"] == 1
    assert "尚未实现" in result.findings[0].message
    assert result.findings[0].flagged_pending_basis is True
