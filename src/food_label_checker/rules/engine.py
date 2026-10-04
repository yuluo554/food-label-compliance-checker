"""规则引擎：规则集版本化，按 check_type 分派，only_if 类目门控对全部类型生效。

schema 详见 plan/04-模块详设.md §2/§4。骨架仅实现 mandatory_field 处理器，
其余 check_type 随 M3 落地；未知类型显式转"待人工确认"，不静默跳过。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import (
    LEVEL_FAIL,
    LEVEL_MANUAL,
    LEVEL_PASS,
    LabelCard,
    Finding,
    RuleResult,
    _LEVEL_STAT,
)

RULESETS_DIR = Path(__file__).resolve().parent / "rulesets"
AVAILABLE_RULESETS = ("gb7718-2011", "gb7718-2025")

_RULESET_ALIAS = {
    "2011": ["gb7718-2011"],
    "2025": ["gb7718-2025"],
    "both": list(AVAILABLE_RULESETS),
}


def resolve_ruleset_ids(spec: str) -> List[str]:
    """把 CLI 的 --ruleset 取值解析为规则集 id 列表。"""
    ids = _RULESET_ALIAS.get(spec)
    if not ids:
        raise ValueError(f"未知规则集选择：{spec}（可选 2011 / 2025 / both）")
    return list(ids)


def load_ruleset(ruleset_id: str) -> Dict[str, Any]:
    """加载规则集 JSON。规则内容以 M3 入库原文核对为准。"""
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

    门控必须对全部 check_type 生效（含未来 conditional 分支）——由调用处统一执行。
    """
    if not only_if:
        return True
    keywords = only_if if isinstance(only_if, list) else [only_if]
    text = _card_text(card)
    return any(k in text for k in keywords)


def _check_mandatory_field(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Finding:
    param = rule["param"]
    fld = card.get(param)
    if fld is not None:
        return Finding(
            rule_id=rule["id"],
            level=LEVEL_PASS,
            message=f"已标示（{rule['name']}）。",
            ruleset_id=ruleset_id,
            basis=rule.get("basis", {}),
            evidence=fld.evidence,
        )
    return Finding(
        rule_id=rule["id"],
        level=LEVEL_FAIL,
        message=f"未检出『{rule['name']}』对应的标示内容（参数 {param}）。",
        ruleset_id=ruleset_id,
        basis=rule.get("basis", {}),
        advice=rule.get("advice", ""),
    )


def _check_unsupported(card: LabelCard, rule: Dict[str, Any], ruleset_id: str) -> Finding:
    return Finding(
        rule_id=rule["id"],
        level=LEVEL_MANUAL,
        message=f"check_type『{rule['check_type']}』尚未实现，转待人工确认。",
        ruleset_id=ruleset_id,
        basis=rule.get("basis", {}),
        advice="等待对应里程碑实现该检查类型（见 plan/05）。",
    )


_HANDLERS = {
    "mandatory_field": _check_mandatory_field,
}


def run_ruleset(card: LabelCard, ruleset: Dict[str, Any]) -> RuleResult:
    """对参数卡跑一个规则集，输出带统计的 RuleResult。"""
    ruleset_id = ruleset["ruleset_id"]
    findings: List[Finding] = []
    stats = {"checked": 0, "skipped": 0, "pass": 0, "fail": 0, "manual": 0}

    for rule in ruleset.get("rules", []):
        if not gate_matches(rule.get("only_if"), card):
            stats["skipped"] += 1
            continue
        stats["checked"] += 1
        handler = _HANDLERS.get(rule["check_type"], _check_unsupported)
        finding = handler(card, rule, ruleset_id)
        if finding is None:
            continue
        finding.flagged_pending_basis = rule.get("basis", {}).get("status") != "已核对"
        findings.append(finding)
        stats[_LEVEL_STAT[finding.level]] += 1

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
