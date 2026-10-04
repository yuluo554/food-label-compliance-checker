"""M2 解析器回归测试（冻结集）。

冻结集文件只读不重生成（决策 D18）；期望参数卡值由生成器内存重建——位级
一致性由 tests/test_datagen_repro.py 守门。覆盖：
- 逐样本全字段值回归（值不等即红，比 F1 门槛更硬）；
- 证据性质：quote 必为输入逐字子串、span 与 quote 逐字节对应（防幻觉硬校验）；
- V7a 契约：非规范日期须解析出日期值，不得升级为「缺生产日期」误报；
- 解析 F1 自测 ≥0.9（plan/05 M2 DoD；M4 全量口径定稿）。
"""
import json
from pathlib import Path

import pytest

from food_label_checker.parser import parse_label

from parse_f1 import (
    FROZEN_DIR,
    build_expected,
    evaluate_frozen,
    load_frozen_dataset,
    num_eq,
    value_eq,
)


@pytest.fixture(scope="module")
def frozen_dataset():
    return load_frozen_dataset()


def _parse_frozen(sample) -> tuple:
    text = (FROZEN_DIR / sample["file"]).read_text(encoding="utf-8")
    return text, parse_label(text)


def test_frozen_full_value_regression(frozen_dataset):
    """逐样本逐字段：解析值必须与生成器期望值全等；V1 删除字段必须缺位。"""
    truth, states = frozen_dataset
    for sample, state in zip(truth["samples"], states):
        _, card = _parse_frozen(sample)
        expected = build_expected(state)
        ctx = f"{sample['sample_id']}({sample['template']})"

        for key, exp in expected.items():
            if key == "nutrition_table":
                rows = {row["name"]: row for row in card.nutrition_table}
                assert len(card.nutrition_table) == len(exp), ctx
                for row in exp:
                    got = rows[row["name"]]
                    assert num_eq(got["amount"], row["amount"]), f"{ctx}.{row['name']}"
                    assert got["unit"] == row["unit"], f"{ctx}.{row['name']}"
                    assert num_eq(got["nrv_percent"], row["nrv_percent"]), f"{ctx}.{row['name']}"
            elif key == "claims":
                assert card.claims == exp, ctx
            else:
                fld = card.get(key)
                assert fld is not None, f"{ctx}: 缺字段 {key}"
                assert value_eq(fld.value, exp), (
                    f"{ctx}.{key}: 解析 {fld.value!r} != 期望 {exp!r}"
                )

        for inj in sample["injections"]:  # V1 删除的字段不得被解析出值
            if inj["type"] == "V1":
                deleted_key = inj["detail"]["deleted_field"]
                assert not card.has(deleted_key), f"{ctx}: {deleted_key} 应缺位"
                assert any(deleted_key in u or "未检出" in u for u in card.unresolved), ctx

        if sample["clean_baseline"]:  # 干净样本：全部强制字段在位，无 unresolved
            assert card.unresolved == [], ctx


def test_evidence_quote_literal_and_span_exact(frozen_dataset):
    """防幻觉硬校验：quote ⊆ 输入，且 text[span] == quote 逐字节对应。"""
    truth, _ = frozen_dataset
    for sample in truth["samples"]:
        text, card = _parse_frozen(sample)
        sid = sample["sample_id"]
        for key, fld in card.fields.items():
            ev = fld.evidence
            assert ev is not None, f"{sid}.{key} 缺证据"
            assert ev.region, f"{sid}.{key} 证据缺区域"
            assert ev.quote and ev.quote in text, f"{sid}.{key} quote 非原文子串"
            assert ev.span is not None, f"{sid}.{key} 证据缺 span"
            s, e = ev.span
            assert text[s:e] == ev.quote, f"{sid}.{key} span 与 quote 不对应"
        for row in card.nutrition_table:
            ev = row["evidence"]
            assert ev["quote"] in text, f"{sid}.nutrition 行 quote 非原文子串"
            s, e = ev["span"]
            assert text[s:e] == ev["quote"], f"{sid}.nutrition 行 span 不对应"
        for claim in card.claims:
            assert claim in text, f"{sid} 声称文本非原文子串"


def test_all_p0_fields_have_evidence(frozen_dataset):
    """证据挂全：参数卡字段表 P0 键解析成功时必带证据（plan/05 M2 DoD）。"""
    truth, _ = frozen_dataset
    p0_keys = {
        "food_name", "ingredients", "net_content", "production_date", "shelf_life",
        "expiry_date", "storage_conditions", "producer_name", "producer_address",
        "producer_contact", "sc_license", "product_standard", "salt_oil_sugar_notice",
    }
    seen_keys = set()
    for sample in truth["samples"]:
        _, card = _parse_frozen(sample)
        for key in card.fields:
            seen_keys.add(key)
    assert seen_keys == p0_keys | {"claims"}, f"P0 键覆盖偏差：{sorted(seen_keys)}"


def test_v7a_nonstandard_date_parsed_not_missing(frozen_dataset):
    """V7a 契约（datagen/__init__.py §6）：非规范日期仍须解析出日期值。

    格式问题归 M3 FMT-DATE-01；解析层不得报「缺生产日期」。
    """
    truth, _ = frozen_dataset
    sample = next(s for s in truth["samples"] if s["sample_id"] == "sample-0011")
    assert any(
        inj["type"] == "V7" and inj["main_expect"]["rule_id"] == "FMT-DATE-01"
        for inj in sample["injections"]
    )
    text, card = _parse_frozen(sample)
    fld = card.get("production_date")
    assert fld is not None, "V7a 样本不得缺生产日期"
    assert fld.value == "2026-09-12"  # 非规范标示 2026/9/12 的日期值
    assert fld.evidence.quote == "2026/9/12"
    assert text[fld.evidence.span[0]:fld.evidence.span[1]] == "2026/9/12"
    assert not any("生产日期：未检出" in u for u in card.unresolved)


def test_parse_f1_frozen_at_least_090():
    """解析 F1 自测（plan/05 M2 DoD：冻结集 ≥0.9）。"""
    metrics, issues = evaluate_frozen()
    print("解析 F1 自测指标：", json.dumps(metrics, ensure_ascii=False))
    if issues:
        print("对账问题（前 10 条）：")
        for line in issues[:10]:
            print("  ", line)
    assert metrics["f1"] >= 0.9, f"F1={metrics['f1']} 低于 DoD 门槛 0.9"
    assert metrics["precision"] >= 0.9 and metrics["recall"] >= 0.9
