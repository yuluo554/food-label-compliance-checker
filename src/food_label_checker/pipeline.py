"""端到端流水线：解析 → （LLM 兜底，可选）→ 双标尺审查 → 对照。

M0 骨架版；M4 加入 LLM 兜底通路：llm_config 启用时对解析缺失的 P0 字段
做 LLM 抽取（quote ⊆ 原文逐字校验，标注 LLM 参与），不可达/超时自动降级
为规则通路既有语义（行在值不可析 → 待人工确认 / 行缺失 → 不合规）。
M5 升级为带节点/边/重试/耗时记录的状态机（plan/03 §1）。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from . import __version__
from .parser import parse_label
from .rules.engine import dual_diff, load_ruleset, run_ruleset


def check_text(text: str, ruleset_ids: List[str], llm_config=None) -> Dict[str, Any]:
    """对一段标签文本执行完整审查，返回可 JSON 序列化的结果。

    llm_config 为 None 或 enabled=False 时完全不感知 LLM（核心通路零 API）。
    """
    card = parse_label(text)

    fallback_report: Dict[str, Any] = {
        "enabled": False,
        "status": "off",
        "reason": "LLM 兜底默认关闭（--llm 或 FOOD_LABEL_LLM_ENABLED 开启）",
    }
    if llm_config is not None and llm_config.enabled:
        from .llm.client import LLMClient
        from .llm.fallback import apply_fallback

        fallback_report = apply_fallback(card, text, LLMClient(llm_config))

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
        "fallback": fallback_report,
        "results": results,
    }
    if len(ruleset_ids) >= 2:
        out["dual_diff"] = dual_diff(rule_results, ruleset_ids[0], ruleset_ids[-1])
    return out


def parse_text(text: str) -> Dict[str, Any]:
    """仅解析为参数卡（flcheck parse 子命令）。"""
    return parse_label(text).to_dict()
