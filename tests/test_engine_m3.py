"""M3 引擎回归：冻结集全量对账（真值 ↔ 双标尺非 pass 集合）、门控词表、
conditional 豁免分支、dual_diff 对照。

对账口径与 datagen/__init__.py 真值语义（D16）一致：干净样本零不合规；注入
样本每把标尺的非 pass 集合 == 真值主期望集合按规则集归属取差（唯一归属
差异：CLAIM-ZEROADD-01 仅 2025——D16 豁免契约）。评测输入一律读冻结文件
的重建文本（generate_dataset_with_states 与冻结 fixtures 位级一致，由
test_datagen_repro 守门），不重生成文件。
"""
import pytest

from food_label_checker.datagen import generate_dataset_with_states
from food_label_checker.models import LEVEL_FAIL, LEVEL_MANUAL
from food_label_checker.parser import parse_label
from food_label_checker.rules.engine import (
    AVAILABLE_RULESETS,
    dual_diff,
    gate_matches,
    load_ruleset,
    run_ruleset,
)

SEED, N = 2026, 12
# 规则集归属差异（D16）：2011 不得对 2025 新增声称限制报不合规
RULESET_EXEMPT = {"gb7718-2011": {"CLAIM-ZEROADD-01"}, "gb7718-2025": set()}


@pytest.fixture(scope="module")
def frozen_dataset():
    return generate_dataset_with_states(SEED, N)


@pytest.fixture(scope="module")
def loaded_rulesets():
    return {rid: load_ruleset(rid) for rid in AVAILABLE_RULESETS}


def _non_pass(result, level=LEVEL_FAIL):
    return {f.rule_id for f in result.findings if f.level == level}


@pytest.mark.parametrize("ruleset_id", AVAILABLE_RULESETS)
def test_frozen_clean_samples_zero_fails(frozen_dataset, loaded_rulesets, ruleset_id):
    """clean_baseline 承诺：干净样本在两把标尺下非 pass（fail）集合为空。"""
    truth, texts, _ = frozen_dataset
    for sample in truth["samples"]:
        if not sample["clean_baseline"]:
            continue
        card = parse_label(texts[sample["file"]])
        result = run_ruleset(card, loaded_rulesets[ruleset_id])
        assert _non_pass(result) == set(), (sample["sample_id"], ruleset_id)


def test_frozen_injected_samples_exact_non_pass(frozen_dataset, loaded_rulesets):
    """注入样本：每把标尺的非 pass 集合与真值主期望精确相等（无误报/漏报）。"""
    truth, texts, _ = frozen_dataset
    for sample in truth["samples"]:
        if sample["clean_baseline"]:
            continue
        card = parse_label(texts[sample["file"]])
        mains = {i["main_expect"]["rule_id"] for i in sample["injections"]}
        for rid, ruleset in loaded_rulesets.items():
            expected = mains - RULESET_EXEMPT[rid]
            result = run_ruleset(card, ruleset)
            got = _non_pass(result)
            assert got == expected, (
                f"{sample['sample_id']} {rid}: got={sorted(got)} exp={sorted(expected)}"
            )


@pytest.mark.parametrize("ruleset_id", AVAILABLE_RULESETS)
def test_no_manual_findings_on_frozen_set(frozen_dataset, loaded_rulesets, ruleset_id):
    """冻结集语料全部可判定：不允许出现待人工确认结论（兜底留给真实世界）。"""
    truth, texts, _ = frozen_dataset
    for sample in truth["samples"]:
        card = parse_label(texts[sample["file"]])
        result = run_ruleset(card, loaded_rulesets[ruleset_id])
        mans = _non_pass(result, LEVEL_MANUAL)
        assert mans == set(), (sample["sample_id"], ruleset_id, sorted(mans))


def test_frozen_dual_diff_only_zeroadd(frozen_dataset, loaded_rulesets):
    """dual_diff 对照回归：仅 V5（零添加）产生 2025 新增不合规，其余对照为空。"""
    truth, texts, _ = frozen_dataset
    for sample in truth["samples"]:
        card = parse_label(texts[sample["file"]])
        results = {rid: run_ruleset(card, r) for rid, r in loaded_rulesets.items()}
        diff = dual_diff(results, "gb7718-2011", "gb7718-2025")
        mains = {i["main_expect"]["rule_id"] for i in sample["injections"]}
        expected_new = ["CLAIM-ZEROADD-01"] if "CLAIM-ZEROADD-01" in mains else []
        assert diff["new_fails"] == expected_new, sample["sample_id"]
        assert diff["resolved_fails"] == []


# ---------------------------------------------------------------------------
# 门控词表（M3 定稿）：品类词互斥，对全部 check_type 生效
# ---------------------------------------------------------------------------

def _clean_cards_by_template():
    truth, texts, _ = generate_dataset_with_states(SEED, 4)  # 前 4 个为干净版
    out = {}
    for sample in truth["samples"]:
        out[sample["template"]] = parse_label(texts[sample["file"]])
    return out


def test_gate_vocabulary_clean_cards(frozen_dataset, loaded_rulesets):
    """门控词表与干净语料互斥：每个门控规则只在其目标品类命中。"""
    truth, texts, _ = frozen_dataset
    cards = {}
    for sample in truth["samples"]:
        if sample["clean_baseline"]:
            cards[sample["template"]] = texts[sample["file"]]
    gated = [
        (rid, rule)
        for rid in AVAILABLE_RULESETS
        for rule in loaded_rulesets[rid]["rules"]
        if rule.get("only_if")
    ]
    assert gated, "规则集应含门控规则（门控词表回归前提）"
    for rid, rule in gated:
        hits = [tpl for tpl, text in cards.items() if gate_matches(rule["only_if"], parse_label(text))]
        assert rule["only_if"] and hits, (rid, rule["id"])
        # 门控命中数应有限（词表互斥：不同品类模板不得同时命中）
        assert len(hits) == 1, (rid, rule["id"], hits)


def test_gate_blocks_gated_rules_on_other_clean_samples(frozen_dataset, loaded_rulesets):
    """其他品类干净样本上，门控规则必须 skipped 而非产生结论。"""
    truth, texts, _ = frozen_dataset
    for sample in truth["samples"]:
        if not sample["clean_baseline"]:
            continue
        card = parse_label(texts[sample["file"]])
        for rid, ruleset in loaded_rulesets.items():
            result = run_ruleset(card, ruleset)
            gated_ids = {r["id"] for r in ruleset["rules"] if r.get("only_if")}
            fired = {f.rule_id for f in result.findings} & gated_ids
            template = sample["template"]
            expected_fired = set()
            if template == "beverage-juice":
                expected_fired = {"ING-ORDER-01"}
            elif template == "dairy-fermented":
                expected_fired = {"ING-ORDER-02"}
            assert fired == expected_fired, (template, rid, sorted(fired))


# ---------------------------------------------------------------------------
# conditional 豁免分支（GB 7718 4.3.1 / 2025 10.1 的确定性近似）
# ---------------------------------------------------------------------------

def _run_one_rule(card, ruleset_id, rule_id):
    ruleset = load_ruleset(ruleset_id)
    rule = next(r for r in ruleset["rules"] if r["id"] == rule_id)
    result = run_ruleset(card, {"ruleset_id": ruleset_id, "rules": [rule]})
    assert len(result.findings) == 1
    return result.findings[0]


def test_conditional_vinegar_shelf_life_exempt():
    """食醋未标保质期 → 2011/2025 均按豁免通过（4.3.1 / 10.1）。"""
    text = (
        "食品名称：鼎醇 酿造食醋\n配料：水、高粱、麸皮\n"
        "生产日期：2026年01月05日\n净含量：500mL\n"
        "生产商：鼎醇调味食品有限公司\n地址：酱湖省酱湖市\n联系方式：400-840-0004\n"
        "食品生产许可证编号：SC10335010004444\n"
    )
    for rid in AVAILABLE_RULESETS:
        finding = _run_one_rule(parse_label(text), rid, "MAND-SHELF-01")
        assert finding.level == "合规", (rid, finding.message)
        assert "豁免" in finding.message


def test_conditional_alcohol_shelf_life_manual():
    """饮料酒未标保质期 → 豁免以酒精度≥10%vol 为条件 → 待人工确认。"""
    text = (
        "食品名称：某啤酒\n配料：水、麦芽、啤酒花\n"
        "生产日期：2026年01月05日\n净含量：500mL\n酒精度：8%vol\n"
        "生产商：某酒业有限公司\n地址：某省某市\n联系方式：400-000-0000\n"
    )
    for rid in AVAILABLE_RULESETS:
        finding = _run_one_rule(parse_label(text), rid, "MAND-SHELF-01")
        assert finding.level == LEVEL_MANUAL, (rid, finding.message)


def test_conditional_dairy_shelf_life_missing_fails():
    """非豁免品类缺保质期 → 不合规（V1 语义）。"""
    text = (
        "食品名称：牧云 发酵乳\n配料：生牛乳、白砂糖\n"
        "生产日期：2026年01月05日\n净含量：200g\n"
        "生产商：牧云乳业有限公司\n地址：云溪省云溪市\n联系方式：400-810-0001\n"
        "食品生产许可证编号：SC10532050001235\n"
    )
    for rid in AVAILABLE_RULESETS:
        finding = _run_one_rule(parse_label(text), rid, "MAND-SHELF-01")
        assert finding.level == LEVEL_FAIL, (rid, finding.message)


def test_conditional_expiry_requires_production_date():
    """2025 到期日豁免前提：未标生产日期的食醋不得豁免到期日（10.1 前提）。"""
    text = (
        "食品名称：鼎醇 酿造食醋\n配料：水、高粱\n净含量：500mL\n"
        "保质期：18个月\n"
        "生产商：鼎醇调味食品有限公司\n地址：酱湖省酱湖市\n联系方式：400-840-0004\n"
        "食品生产许可证编号：SC10335010004444\n"
    )
    finding = _run_one_rule(parse_label(text), "gb7718-2025", "MAND-EXPIRY-01")
    assert finding.level == LEVEL_FAIL


# ---------------------------------------------------------------------------
# 确定性检查单元（引擎 handler 层补充覆盖）
# ---------------------------------------------------------------------------

def test_format_rule_flags_slash_date_and_passes_canonical():
    """FMT-DATE-01：斜杠式（月未补零）报不合规；规范中式格式通过。"""
    bad = parse_label("生产日期：2026/9/12\n")
    good = parse_label("生产日期：2026年09月12日\n")
    f_bad = _run_one_rule(bad, "gb7718-2011", "FMT-DATE-01")
    f_good = _run_one_rule(good, "gb7718-2011", "FMT-DATE-01")
    assert f_bad.level == LEVEL_FAIL
    assert "2026/9/12" in f_bad.message
    assert f_good.level == "合规"


def test_format_rule_not_run_when_field_missing():
    card = parse_label("食品名称：测试\n")
    result = run_ruleset(card, {"ruleset_id": "t", "rules": [dict(
        load_ruleset("gb7718-2011")["rules"][0],
        id="FMT-X", check_type="format", param="production_date")]})
    assert result.stats["not_run"] == 1


def test_date_logic_flags_shifted_expiry():
    """V7b 语义：到期日与生产日期+保质期矛盾 → DATE-LOGIC-01 不合规。"""
    text = (
        "生产日期：2026年09月12日\n保质期：10个月\n保质期到期日：2027年06月12日\n"
    )
    finding = _run_one_rule(parse_label(text), "gb7718-2011", "DATE-LOGIC-01")
    assert finding.level == LEVEL_FAIL
    assert "2027-07-12" in finding.message  # 推算值 = 2026-09-12 + 10 个月


def test_date_logic_not_run_without_expiry():
    card = parse_label("生产日期：2026年09月12日\n保质期：10个月\n")
    result = run_ruleset(card, load_ruleset("gb7718-2011"))
    # not_run：前置缺失不产生结论（缺失由强制标示规则覆盖）
    assert "DATE-LOGIC-01" not in {f.rule_id for f in result.findings}


def test_date_logic_unknown_shelf_unit_manual():
    card = parse_label("生产日期：2026年09月12日\n保质期：2年\n保质期到期日：2028年09月12日\n")
    finding = _run_one_rule(card, "gb7718-2011", "DATE-LOGIC-01")
    assert finding.level == LEVEL_MANUAL


def test_nrv_recalc_multi_row_findings():
    """行级结论：两行 NRV% 算错 → 同一规则两条不合规 finding。"""
    # 复算基准：能量 1000kJ→12%，蛋白质 10g→17%，碳水 50g→17%
    text = (
        "营养成分表\n项目\t每100g\tNRV%\n"
        "能量\t1000kJ\t20%\n蛋白质\t10.0g\t8%\n碳水化合物\t50.0g\t17%\n"
    )
    card = parse_label(text)
    result = run_ruleset(card, {"ruleset_id": "t", "rules": [dict(
        load_ruleset("gb7718-2011")["rules"][0],
        id="NRV-X", check_type="nrv_recalc", param="nutrition_table")]})
    fails = [f for f in result.findings if f.level == LEVEL_FAIL]
    assert len(fails) == 2  # 能量 20%≠12、蛋白质 8%≠17（碳水一致不报）
    assert {f.rule_id for f in fails} == {"NRV-X"}


def test_claim_threshold_missing_sugar_row_manual():
    """声称无糖但营养成分表缺糖行 → 无法复算转人工（2011 §4.2 语义交人工）。"""
    text = "声称：无糖\n营养成分表\n项目\t每100g\tNRV%\n能量\t100kJ\t1%\n"
    finding = _run_one_rule(parse_label(text), "gb7718-2011", "CLAIM-THRESH-01")
    assert finding.level == LEVEL_MANUAL
