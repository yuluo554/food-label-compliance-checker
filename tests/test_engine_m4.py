"""M4 引擎回归：2025 新规则（NUTR-ROWS-01/ALLERGEN-01）+ 行在值不可析降级语义。

D22（plan/06）：①nutrition_rows / allergen_notice 两个新 check_type；②
unresolved_detail[param]=="present_unparsed"（标示行存在但解析失败）的强制/
条件规则转"待人工确认"而非不合规——可能是解析覆盖不足而非标签违规；行整体
缺失仍判不合规（V1 语义）。LLM 兜底由 pipeline 层负责回填，规则层不感知。
"""
import pytest

from food_label_checker.datagen import generate_dataset_with_states
from food_label_checker.models import LEVEL_FAIL, LEVEL_MANUAL, LEVEL_PASS
from food_label_checker.parser import parse_label
from food_label_checker.rules.engine import (
    AVAILABLE_RULESETS,
    load_ruleset,
    run_ruleset,
)

SEED, N = 2026, 12


def _run_one_rule(card, ruleset_id, rule_id):
    ruleset = load_ruleset(ruleset_id)
    rule = next(r for r in ruleset["rules"] if r["id"] == rule_id)
    result = run_ruleset(card, {"ruleset_id": ruleset_id, "rules": [rule]})
    assert len(result.findings) == 1
    return result.findings[0]


# ---------------------------------------------------------------------------
# NUTR-ROWS-01：强制营养行完整性（GB 28050-2025 §4.1）
# ---------------------------------------------------------------------------

def _nutrition_table(names):
    lines = ["营养成分表", "项目\t每100g\tNRV%"]
    for i, name in enumerate(names):
        lines.append(f"{name}\t{1 + i}g\t1%")
    return "\n".join(lines) + "\n"


def test_nutrition_rows_missing_sugar_row_fails():
    """缺糖行 → 行级不合规（其余行不连坐）。"""
    card = parse_label(_nutrition_table(["能量", "蛋白质", "脂肪", "饱和脂肪", "碳水化合物", "钠"]))
    finding = _run_one_rule(card, "gb7718-2025", "NUTR-ROWS-01")
    assert finding.level == LEVEL_FAIL
    assert "糖" in finding.message


def test_nutrition_rows_complete_passes_and_multi_missing_reports_each():
    full = ["能量", "蛋白质", "脂肪", "饱和脂肪", "碳水化合物", "糖", "钠"]
    assert _run_one_rule(parse_label(_nutrition_table(full)), "gb7718-2025",
                         "NUTR-ROWS-01").level == LEVEL_PASS

    card = parse_label(_nutrition_table(["能量"]))
    result = run_ruleset(card, {"ruleset_id": "t", "rules": [dict(
        next(r for r in load_ruleset("gb7718-2025")["rules"] if r["id"] == "NUTR-ROWS-01"))]})
    fails = [f for f in result.findings if f.level == LEVEL_FAIL]
    assert len(fails) == 6  # 缺 6 行 → 6 条行级结论


def test_nutrition_rows_not_run_when_table_absent():
    """表整体缺失 → not_run（由 NUTR-TABLE-01 覆盖），不产生重复结论。"""
    card = parse_label("食品名称：测试乳\n")
    result = run_ruleset(card, {"ruleset_id": "t", "rules": [dict(
        next(r for r in load_ruleset("gb7718-2025")["rules"] if r["id"] == "NUTR-ROWS-01"))]})
    assert result.stats["not_run"] == 1
    assert result.findings == []


def test_nutrition_rows_2025_only_and_frozen_clean_pass():
    """新规则仅 2025；冻结集干净样本（v2 全 7 行）在 2025 下必须通过。"""
    assert "NUTR-ROWS-01" not in {r["id"] for r in load_ruleset("gb7718-2011")["rules"]}
    _, texts, _ = generate_dataset_with_states(SEED, 4)  # 前 4 个为干净版
    rule = dict(next(r for r in load_ruleset("gb7718-2025")["rules"]
                     if r["id"] == "NUTR-ROWS-01"))
    for text in texts.values():
        result = run_ruleset(parse_label(text), {"ruleset_id": "t", "rules": [rule]})
        assert result.stats["pass"] == 1 and result.stats["fail"] == 0


# ---------------------------------------------------------------------------
# ALLERGEN-01：致敏物质提示（GB 7718-2025 §4.12）
# ---------------------------------------------------------------------------

def test_allergen_fail_when_allergen_ingredient_without_notice():
    card = parse_label("食品名称：测试乳\n配料：水、生牛乳、白砂糖\n")
    finding = _run_one_rule(card, "gb7718-2025", "ALLERGEN-01")
    assert finding.level == LEVEL_FAIL
    assert "乳" in finding.message


def test_allergen_pass_with_notice_or_without_allergen_ingredients():
    with_notice = parse_label("食品名称：测试乳\n配料：水、生牛乳\n致敏物质提示：含乳。\n")
    assert _run_one_rule(with_notice, "gb7718-2025", "ALLERGEN-01").level == LEVEL_PASS

    no_allergen = parse_label("食品名称：苹果汁\n配料：水、苹果汁\n")
    assert _run_one_rule(no_allergen, "gb7718-2025", "ALLERGEN-01").level == LEVEL_PASS


def test_allergen_keyword_search_scoped_to_ingredients():
    """『蛋白质』出现在营养表不触发（检索范围仅配料表，防误报）。"""
    card = parse_label(
        "食品名称：柠檬红茶\n配料：水、红茶茶叶\n"
        "营养成分表\n项目\t每100mL\tNRV%\n蛋白质\t0.2g\t0%\n"
    )
    assert _run_one_rule(card, "gb7718-2025", "ALLERGEN-01").level == LEVEL_PASS


def test_allergen_2025_only_and_frozen_clean_pass():
    assert "ALLERGEN-01" not in {r["id"] for r in load_ruleset("gb7718-2011")["rules"]}
    _, texts, _ = generate_dataset_with_states(SEED, 4)
    rule = dict(next(r for r in load_ruleset("gb7718-2025")["rules"]
                     if r["id"] == "ALLERGEN-01"))
    for text in texts.values():
        result = run_ruleset(parse_label(text), {"ruleset_id": "t", "rules": [rule]})
        assert result.stats["pass"] == 1 and result.stats["fail"] == 0


# ---------------------------------------------------------------------------
# 行在值不可析 → 待人工确认（unresolved_detail 降级语义，D22）
# ---------------------------------------------------------------------------

def test_present_unparsed_mandatory_goes_manual_not_fail():
    """净含量行存在但解析失败 → 待人工确认；行整体缺失 → 不合规（V1 语义不变）。"""
    card = parse_label("食品名称：测试乳\n净含量：计量称重\n")
    assert card.unresolved_detail.get("net_content") == "present_unparsed"
    finding = _run_one_rule(card, "gb7718-2011", "MAND-NET-01")
    assert finding.level == LEVEL_MANUAL

    absent = parse_label("食品名称：测试乳\n")
    finding_absent = _run_one_rule(absent, "gb7718-2011", "MAND-NET-01")
    assert finding_absent.level == LEVEL_FAIL


def test_present_unparsed_conditional_expiry_goes_manual():
    """到期日行存在但日期不可析 → 2025 MAND-EXPIRY-01 待人工确认。"""
    card = parse_label("保质期到期日：见瓶身\n生产日期：2026年09月12日\n")
    assert card.unresolved_detail.get("expiry_date") == "present_unparsed"
    finding = _run_one_rule(card, "gb7718-2025", "MAND-EXPIRY-01")
    assert finding.level == LEVEL_MANUAL


def test_unresolved_detail_cleared_after_retry_success():
    """失败行后另一行成功 → 字段在位，detail 标记撤销。"""
    card = parse_label("净含量：计量称重\n净含量：250 mL\n")
    assert card.get("net_content").value == {"amount": 250.0, "unit": "mL"}
    assert "net_content" not in card.unresolved_detail


def test_frozen_set_still_no_manual_findings():
    """冻结集（v2）全部可判定：降级分支不得在正常语料上触发。"""
    from food_label_checker.rules.engine import run_ruleset as run
    truth, texts, _ = generate_dataset_with_states(SEED, N)
    for sample in truth["samples"]:
        card = parse_label(texts[sample["file"]])
        for rid in AVAILABLE_RULESETS:
            res = run(card, load_ruleset(rid))
            mans = {f.rule_id for f in res.findings if f.level == LEVEL_MANUAL}
            assert mans == set(), (sample["sample_id"], rid, sorted(mans))
