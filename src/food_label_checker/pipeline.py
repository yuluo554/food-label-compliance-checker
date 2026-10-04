"""端到端流水线：解析 → 双标尺审查 → 对照。

M0 骨架版；M5 升级为带节点/边/重试/耗时记录的状态机（plan/03 §1）。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from . import __version__
from .parser import parse_label
from .rules.engine import dual_diff, load_ruleset, run_ruleset


def check_text(text: str, ruleset_ids: List[str]) -> Dict[str, Any]:
    """对一段标签文本执行完整审查，返回可 JSON 序列化的结果。"""
    card = parse_label(text)

    rule_results = {rid: run_ruleset(card, load_ruleset(rid)) for rid in ruleset_ids}

    results = {
        rid: {
            "stats": result.stats,
            "findings": [asdict(f) for f in result.findings],
        }
        for rid, result in rule_results.items()
    }

    out: Dict[str, Any] = {
        "engine_version": __version__,
        "ruleset_ids": list(ruleset_ids),
        "card": card.to_dict(),
        "results": results,
    }
    if len(ruleset_ids) >= 2:
        out["dual_diff"] = dual_diff(rule_results, ruleset_ids[0], ruleset_ids[-1])
    return out


def parse_text(text: str) -> Dict[str, Any]:
    """仅解析为参数卡（flcheck parse 子命令）。"""
    return parse_label(text).to_dict()
