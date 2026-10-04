"""规则引擎：规则集版本化，按 check_type 分派，only_if 类目门控对全部类型生效。

M3 全类型落地（plan/04 §2/§4）：
- check_type 全集（9 种）：mandatory_field / format / nrv_recalc /
  energy_consistency / ingredient_order / claim_threshold / claim_whitelist /
  date_logic / conditional；未知类型显式转"待人工确认"，不静默跳过。
- 处理器返回 Finding 列表（行级结论如 NRV% 复算可一规则多 finding）；
  返回 None 表示前置缺失无法执行，计入 stats["not_run"]（不产生结论）。
- stats 口径：pass + fail + manual == checked == len(findings)；skipped 为
  门控未命中跳过数；not_run 为前置缺失未执行数。
- 门控纪律：only_if 为 None 恒真；否则关键词任一命中卡片平文本即真，对
  全部 check_type 生效。M3 门控词表定稿（与规则集 JSON 一致）：
  品类/品名特征词（果汁饮料、发酵乳、酸乳）与豁免判定词（食醋、食用盐、
  味精、固态食糖、酒精度、饮料酒、葡萄酒、啤酒、黄酒、白酒、米酒）。
- 依据纪律：basis.status != "已核对" 的规则产出结论自动置
  flagged_pending_basis（报告与 Web 同步显示"依据待核对"）。

conditional 语义（GB 7718 豁免条款的确定性近似）：字段缺失时按 params
依次判定——manual_if_any 命中 → 待人工确认（如酒类豁免以酒精度≥10%vol 为
条件，需人工核验度数）；exempt_if_any 命中（且 require_production_date
成立时生产日期在场）→ 豁免通过；否则不合规。params 见规则集 JSON。
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import (
    LEVEL_FAIL,
    LEVEL_MANUAL,
    LEVEL_PASS,
    LabelCard,
    Evidence,
    Finding,
    RuleResult,
    _LEVEL_STAT,
)
from ..numeric import (
    check_energy_consistency,
    check_nrv_rows,
    claim_threshold_checks,
    compute_expected_expiry,
)

RULESETS_DIR = Path(__file__).resolve().parent / "rulesets"
AVAILABLE_RULESETS = ("gb7718-2011", "gb7718-2025")

_RULESET_ALIAS = {
    "2011": ["gb7718-2011"],
    "2025": ["gb7718-2025"],
    "both": list(AVAILABLE_RULESETS),
}

# M2/D19 契约：规范日期标示形式（FMT-DATE 规则的默认判定式）
CANONICAL_DATE_PATTERN = r"\d{4}年\d{2}月\d{2}日"


def resolve_ruleset_ids(spec: str) -> List[str]:
    """把 CLI 的 --ruleset 取值解析为规则集 id 列表。"""
    ids = _RULESET_ALIAS.get(spec)
    if not ids:
        raise ValueError(f"未知规则集选择：{spec}（可选 2011 / 2025 / both）")
    return list(ids)


def load_ruleset(ruleset_id: str) -> Dict[str, Any]:
    """加载规则集 JSON。依据挂 data/knowledge/blocks/ 条文块（quote_ref）。"""
    path = RULESETS_DIR / f"{ruleset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"规则集不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _card_text(card: LabelCard) -> str:
    """把参数卡序列化为门控匹配用的平文本。"""
    parts: List[str] = []
    for f in card.fields.values():
        parts.append(str(f.value))
        if f.evidence is not None:
            parts.append(f.evidence.quote)
    parts.extend(card.ingredients)
    parts.extend(card.claims)
    parts.extend(str(row) for row in card.nutrition_table)
    return "\n".join(parts)


def gate_matches(only_if: Optional[Any], card: LabelCard) -> bool:
    """类目隔离门控：only_if 为 None 恒真；否则任一关键词命中即真。

    门控必须对全部 check_type 生效（含 conditional 分支）——由调用处统一执行。
    """
    if not only_if:
        return True
    keywords = only_if if isinstance(only_if, list) else [only_if]
    text = _card_text(card)
    return any(k in text for k in keywords)


def _evidence_of(card: LabelCard, param: str) -> Optional[Evidence]:
    fld = card.get(param)
    return fld.evidence if fld is not None else None


def _row_evidence(row: Dict[str, Any]) -> Optional[Evidence]:
    ev = row.get("evidence")
    if isinstance(ev, dict):
        return Evidence(
            region=ev.get("region", "营养成分表"),
            quote=ev.get("quote", ""),
            span=tuple(ev["span"]) if ev.get("span") else None,
        )
    return None


def _finding(rule: Dict[str, Any], ruleset_id: str, level: str, message: str,
             evidence: Optional[Evidence] = None, advice: Optional[str] = None) -> Finding:
    return Finding(
        rule_id=rule["id"],
        level=level,
        message=message,
        ruleset_id=ruleset_id,
        basis=rule.get("basis", {}),
        evidence=evidence,
        advice=advice if advice is not None else rule.get("advice", ""),
    )


# ---------------------------------------------------------------------------
# check_type 处理器：返回 Finding 列表；返回 None = 前置缺失，not_run
# ---------------------------------------------------------------------------

def _check_mandatory_field(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    param = rule["param"]
    if param == "nutrition_table":  # D19：营养表为顶层列表，不在 fields
        present = bool(card.nutrition_table)
        evidence = None
    else:
        fld = card.get(param)
        present = fld is not None
        evidence = fld.evidence if fld is not None else None
    if present:
        return [_finding(rule, ruleset_id, LEVEL_PASS, f"已标示（{rule['name']}）。", evidence)]
    return [_finding(
        rule, ruleset_id, LEVEL_FAIL,
        f"未检出『{rule['name']}』对应的标示内容（参数 {param}）。",
    )]


def _check_conditional(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """带豁免/人工分支的标示要求（2011 §4.3.1 / 2025 §10.1 豁免条款）。"""
    params = rule.get("params", {})
    param = rule["param"]
    fld = card.get(param)
    if fld is not None:
        return [_finding(rule, ruleset_id, LEVEL_PASS, f"已标示（{rule['name']}）。", fld.evidence)]

    text = _card_text(card)
    for kw in params.get("manual_if_any", []):
        if kw in text:
            return [_finding(
                rule, ruleset_id, LEVEL_MANUAL,
                f"未标示『{rule['name']}』，且标签含『{kw}』：豁免与否需人工判定。"
                + params.get("manual_note", ""),
            )]
    exempt_hit = next((kw for kw in params.get("exempt_if_any", []) if kw in text), None)
    if exempt_hit is not None:
        if params.get("require_production_date") and card.get("production_date") is None:
            pass  # 豁免前提（已标示生产日期）不成立 → 继续按未标示处理
        else:
            return [_finding(
                rule, ruleset_id, LEVEL_PASS,
                f"未标示『{rule['name']}』，但标签含『{exempt_hit}』，属标准豁免标示情形。",
            )]
    return [_finding(
        rule, ruleset_id, LEVEL_FAIL,
        f"未检出『{rule['name']}』对应的标示内容（参数 {param}），且不属于可豁免情形。",
    )]


def _check_format(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """标示格式核验：对 evidence.quote 全字匹配 params.pattern（缺省规范日期式）。"""
    fld = card.get(rule["param"])
    if fld is None or fld.evidence is None:
        return None  # 缺失由强制标示规则覆盖，格式规则不运行
    pattern = rule.get("params", {}).get("pattern", CANONICAL_DATE_PATTERN)
    expect_desc = rule.get("params", {}).get("expect_desc", "YYYY年MM月DD日")
    quote = fld.evidence.quote
    if re.fullmatch(pattern, quote):
        return [_finding(rule, ruleset_id, LEVEL_PASS,
                         f"标示格式规范：『{quote}』。", fld.evidence)]
    return [_finding(
        rule, ruleset_id, LEVEL_FAIL,
        f"标示格式不规范：『{quote}』不符合{expect_desc}形式"
        f"（{rule.get('params', {}).get('format_note', '应按年月日顺序、月日两位标示')}）。",
        fld.evidence,
    )]


def _check_nrv_recalc(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """NRV% 行级复算（修约间隔 1，容差 ±1）；每份标示行转待人工确认。"""
    if not card.nutrition_table:
        return None
    findings: List[Finding] = []
    per_serving = [r for r in card.nutrition_table
                   if r.get("per_serving") and r.get("nrv_percent") is not None]
    for row in per_serving:
        findings.append(_finding(
            rule, ruleset_id, LEVEL_MANUAL,
            f"营养行『{row.get('name')}』按每份标示，NRV% 无法按每100g(mL)复算，转待人工确认。",
            _row_evidence(row),
        ))
    mismatches = check_nrv_rows(card)
    for m in mismatches:
        findings.append(_finding(
            rule, ruleset_id, LEVEL_FAIL,
            f"营养行『{m['name']}』NRV% 标示 {m['shown']}%，按含量复算应为 {m['recomputed']}%"
            f"（偏差 {m['diff']:+.0f} 个百分点，超修约容差 ±1）。",
            _row_evidence(m),
        ))
    if findings:
        return findings
    checked = sum(1 for r in card.nutrition_table if r.get("nrv_percent") is not None)
    return [_finding(rule, ruleset_id, LEVEL_PASS,
                     f"营养成分表 {checked} 行 NRV% 复算一致（修约间隔 1）。")]


def _check_energy_consistency(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """能量折算一致性：E=round(17P+37F+17C) vs 标示能量（表2 低报方向）。"""
    if not card.nutrition_table:
        return None
    names = ("能量", "蛋白质", "脂肪", "碳水化合物")
    rows = {n: next((r for r in card.nutrition_table if r.get("name") == n), None) for n in names}
    if any(rows[n] is None for n in names):
        return None
    if any(rows[n].get("per_serving") for n in names):
        return [_finding(rule, ruleset_id, LEVEL_MANUAL,
                         "营养成分表按每份标示，能量折算一致性无法按每100g(mL)复算，转待人工确认。")]
    result = check_energy_consistency(card)
    if result is None:  # 单位/数值形态不可复算
        return [_finding(rule, ruleset_id, LEVEL_MANUAL,
                         "能量或供能成分含量单位/数值形态无法复算，转待人工确认。",
                         _row_evidence(rows["能量"]))]
    if result["verdict"] == "violation":
        return [_finding(
            rule, ruleset_id, LEVEL_FAIL,
            f"能量标示 {result['shown_energy_kj']} kJ，按蛋白质/脂肪/碳水化合物含量折算应为 "
            f"{result['recomputed_energy_kj']} kJ，超出允许误差（实际值 ≤120% 标示值，表2）。",
            _row_evidence(rows["能量"]),
        )]
    return [_finding(rule, ruleset_id, LEVEL_PASS,
                     f"能量标示值与折算值一致（折算 {result['recomputed_energy_kj']} kJ，"
                     "系数 17/37/17，2025 §2.3）。")]


def _check_ingredient_order(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """配料递减序先验对：规则 params.ordered_pairs 内的已知先后关系被颠倒才报。"""
    fld = card.get("ingredients")
    if fld is None:
        return None
    items = card.ingredients
    pairs = rule.get("params", {}).get("ordered_pairs", [])
    for before, after in pairs:
        if before in items and after in items and items.index(before) > items.index(after):
            return [_finding(
                rule, ruleset_id, LEVEL_FAIL,
                f"配料『{after}』标示在『{before}』之前：两者均属加入量 >2% 的主配料"
                f"（品类配方先验），不符合加入量递减顺序要求。",
                fld.evidence,
            )]
    return [_finding(rule, ruleset_id, LEVEL_PASS,
                     "配料表未检出可判定的递减序错误（先验对全部有序或不适用）。", fld.evidence)]


def _check_claim_threshold(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """营养声称阈值核验（阈值表读 nutrient_reference.claim_thresholds）。"""
    if not card.claims:
        return [_finding(rule, ruleset_id, LEVEL_PASS, "未检出营养声称，无需阈值核验。")]
    checks = claim_threshold_checks(card)
    findings: List[Finding] = []
    for c in checks:
        if c["verdict"] == "fail":
            findings.append(_finding(
                rule, ruleset_id, LEVEL_FAIL,
                f"声称『{c['claim']}』不成立：{c['nutrient']}含量 {c['amount']}"
                f"{c['unit']}/100g(mL)，超过该声称阈值 ≤{c['max_per_100']}{c['unit']}/100g(mL)"
                "（表C.1，已核对）。",
                _row_evidence(c) if c.get("evidence") else None,
            ))
        elif c["verdict"] in ("no_row", "per_serving"):
            findings.append(_finding(
                rule, ruleset_id, LEVEL_MANUAL,
                f"声称『{c['claim']}』的 {c['nutrient']}含量无法从营养成分表复算"
                f"（{'缺该行' if c['verdict'] == 'no_row' else '按份标示'}），转待人工确认。",
                _row_evidence(c) if c.get("evidence") else None,
            ))
    if findings:
        return findings
    hit = "、".join(sorted({c['claim_contains'] for c in checks})) or "无"
    return [_finding(rule, ruleset_id, LEVEL_PASS,
                     f"声称阈值核验通过（命中阈值项：{hit}）。")]


def _check_claim_whitelist(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """声称用语核验：params.forbidden_terms 内的禁用语出现在声称中即不合规。"""
    if not card.claims:
        return [_finding(rule, ruleset_id, LEVEL_PASS, "未检出声称用语，无需核验。")]
    params = rule.get("params", {})
    forbidden = params.get("forbidden_terms", [])
    kind = params.get("term_kind", "禁用语")
    hits: List[str] = []
    for claim in card.claims:
        matched = [t for t in forbidden if t in claim]
        if matched:
            hits.append(f"『{claim}』（命中{'、'.join(matched)}）")
    if hits:
        return [_finding(
            rule, ruleset_id, LEVEL_FAIL,
            f"检出{kind}声称：{'；'.join(hits)}。",
            card.get("claims").evidence if card.get("claims") is not None else None,
        )]
    return [_finding(rule, ruleset_id, LEVEL_PASS,
                     f"声称用语核验通过（{len(card.claims)} 条声称未命中{kind}）。")]


def _check_date_logic(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    """日期逻辑自洽：到期日 = 生产日期 + 保质期（生成器约定口径，D16）。"""
    prod = card.get("production_date")
    shelf = card.get("shelf_life")
    expiry = card.get("expiry_date")
    if prod is None or shelf is None or expiry is None:
        return None  # 缺失由强制标示规则覆盖；不自洽性缺输入不运行
    shelf_value = shelf.value.get("value") if isinstance(shelf.value, dict) else None
    shelf_unit = shelf.value.get("unit") if isinstance(shelf.value, dict) else None
    if shelf_value is None or shelf_unit is None:
        return [_finding(rule, ruleset_id, LEVEL_MANUAL,
                         "保质期标示无法解析出『数值+单位』，到期日自洽性转待人工确认。")]
    try:
        expected = compute_expected_expiry(str(prod.value), shelf_value, shelf_unit)
    except (ValueError, TypeError):
        return [_finding(rule, ruleset_id, LEVEL_MANUAL,
                         f"保质期单位『{shelf_unit}』暂不支持自动推算，转待人工确认。")]
    try:
        shown = date.fromisoformat(str(expiry.value))
    except (ValueError, TypeError):
        return [_finding(rule, ruleset_id, LEVEL_MANUAL,
                         "保质期到期日无法解析为日期，自洽性转待人工确认。")]
    if shown == expected:
        return [_finding(rule, ruleset_id, LEVEL_PASS,
                         f"到期日自洽：生产日期 {prod.value} + 保质期 {shelf_value}{shelf_unit}"
                         f" = {expected.isoformat()}。", expiry.evidence)]
    return [_finding(
        rule, ruleset_id, LEVEL_FAIL,
        f"日期逻辑矛盾：标示到期日 {shown.isoformat()}，按生产日期 {prod.value} + 保质期 "
        f"{shelf_value}{shelf_unit} 推算应为 {expected.isoformat()}。",
        expiry.evidence,
    )]


def _check_unsupported(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Optional[List[Finding]]:
    return [_finding(
        rule, ruleset_id, LEVEL_MANUAL,
        f"check_type『{rule['check_type']}』尚未实现，转待人工确认。",
        advice="等待对应里程碑实现该检查类型（见 plan/05）。",
    )]


_HANDLERS = {
    "mandatory_field": _check_mandatory_field,
    "conditional": _check_conditional,
    "format": _check_format,
    "nrv_recalc": _check_nrv_recalc,
    "energy_consistency": _check_energy_consistency,
    "ingredient_order": _check_ingredient_order,
    "claim_threshold": _check_claim_threshold,
    "claim_whitelist": _check_claim_whitelist,
    "date_logic": _check_date_logic,
}


def run_ruleset(card: LabelCard, ruleset: Dict[str, Any]) -> RuleResult:
    """对参数卡跑一个规则集，输出带统计的 RuleResult。"""
    ruleset_id = ruleset["ruleset_id"]
    findings: List[Finding] = []
    stats = {"checked": 0, "skipped": 0, "not_run": 0, "pass": 0, "fail": 0, "manual": 0}

    for rule in ruleset.get("rules", []):
        if not gate_matches(rule.get("only_if"), card):
            stats["skipped"] += 1
            continue
        handler = _HANDLERS.get(rule["check_type"], _check_unsupported)
        produced = handler(card, rule, ruleset_id)
        if not produced:  # None / 空列表 → 前置缺失未运行
            stats["not_run"] += 1
            continue
        pending = rule.get("basis", {}).get("status") != "已核对"
        for finding in produced:
            finding.flagged_pending_basis = pending
            findings.append(finding)
            stats[_LEVEL_STAT[finding.level]] += 1
        stats["checked"] += 1

    return RuleResult(ruleset_id=ruleset_id, findings=findings, stats=stats)


def run_dual(card: LabelCard, ruleset_ids: List[str]) -> Dict[str, RuleResult]:
    """同一参数卡分别跑多个规则集（双标尺）。"""
    return {rid: run_ruleset(card, load_ruleset(rid)) for rid in ruleset_ids}


def dual_diff(
    results: Dict[str, RuleResult], baseline_id: str, target_id: str
) -> Dict[str, Any]:
    """新旧规则集不合规项对照：target 相对 baseline 新增/消除的不合规规则。"""
    base_fails = {
        f.rule_id for f in results[baseline_id].findings if f.level == LEVEL_FAIL
    }
    target_fails = {
        f.rule_id for f in results[target_id].findings if f.level == LEVEL_FAIL
    }
    return {
        "baseline": baseline_id,
        "target": target_id,
        "new_fails": sorted(target_fails - base_fails),
        "resolved_fails": sorted(base_fails - target_fails),
    }
