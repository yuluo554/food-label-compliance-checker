"""端到端流水线（M5 状态机）：load_input → parse → llm 兜底（可选）→ run_ruleset×N → merge+diff → emit。

M0 骨架版；M4 加入 LLM 兜底通路；M5 升级为带节点/状态/耗时记录的状态机
（plan/03 §1、plan/04 §5）：

- 每个节点记录 status（ok / skipped / degraded）与 elapsed_ms，随结果 JSON 的
  ``pipeline.nodes`` 返回，另有 ``warnings`` 汇总所有降级节点（供 CLI 打印）；
- 输入类失败（缺文件/坏编码）以异常明确报错退出（CLI 映射退出码 2）；
- 规则类失败降级为该 ruleset 结果缺失 + 警告节点：异常信息原样记入 trace
  detail（不吞异常），其余 ruleset 结果与 merge+diff 正常继续。
"""
from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .parser import parse_label
from .rules.engine import dual_diff, load_ruleset, run_ruleset

# 节点状态（plan/04 §5）
NODE_OK = "ok"
NODE_SKIPPED = "skipped"
NODE_DEGRADED = "degraded"

# 结果 JSON 顶层键（check_text 契约，M4 固化 + M5 追加 pipeline/warnings）
_RESULT_KEYS = ("engine_version", "ruleset_ids", "card", "fallback")


def read_input(raw: Any) -> str:
    """load_input 节点：读入 UTF-8（容忍 BOM）标签文本文件。

    输入类失败以异常明确报错退出：缺文件 FileNotFoundError、坏编码 ValueError，
    由 CLI 捕获映射为退出码 2。
    """
    path = Path(raw)
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在：{path}")
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"输入文件需为 UTF-8 编码：{exc}") from exc


class _Tracer:
    """节点计时与状态记录（结果 JSON 的 pipeline.nodes）。"""

    def __init__(self) -> None:
        self.nodes: List[Dict[str, Any]] = []

    def record(self, node: str, status: str, elapsed_ms: float, detail: str = "") -> None:
        self.nodes.append(
            {
                "node": node,
                "status": status,
                "elapsed_ms": round(elapsed_ms, 3),
                "detail": detail,
            }
        )

    @property
    def warnings(self) -> List[str]:
        return [
            f"{n['node']} 降级：{n['detail']}"
            for n in self.nodes
            if n["status"] == NODE_DEGRADED
        ]


def run_pipeline(
    input_path=None,
    text: Optional[str] = None,
    ruleset_ids: Optional[List[str]] = None,
    llm_config=None,
) -> Dict[str, Any]:
    """状态机主入口。input_path 与 text 二选一（input_path 走 load_input 节点）。"""
    if ruleset_ids is None:
        ruleset_ids = ["gb7718-2011", "gb7718-2025"]
    tr = _Tracer()

    # ---- 节点 1：load_input ------------------------------------------------
    if input_path is not None:
        t0 = time.perf_counter()
        text = read_input(input_path)
        tr.record(
            "load_input", NODE_OK, (time.perf_counter() - t0) * 1000,
            f"读取 {Path(input_path).as_posix()}（{len(text)} 字符）",
        )
    else:
        tr.record("load_input", NODE_SKIPPED, 0.0, "文本由调用方内存提供")

    # ---- 节点 2：parse ------------------------------------------------------
    t0 = time.perf_counter()
    card = parse_label(text)
    tr.record(
        "parse", NODE_OK, (time.perf_counter() - t0) * 1000,
        f"字段 {len(card.fields)} 项 / 营养行 {len(card.nutrition_table)} / "
        f"未解析 {len(card.unresolved)}（LLM 参与标注：{card.llm_assisted}）",
    )

    # ---- 节点 3：llm 兜底（可选）--------------------------------------------
    fallback_report: Dict[str, Any] = {
        "enabled": False,
        "status": "off",
        "reason": "LLM 兜底默认关闭（--llm 或 FOOD_LABEL_LLM_ENABLED 开启）",
    }
    if llm_config is not None and llm_config.enabled:
        t0 = time.perf_counter()
        from .llm.client import LLMClient
        from .llm.fallback import apply_fallback

        fallback_report = apply_fallback(card, text, LLMClient(llm_config))
        status = NODE_DEGRADED if fallback_report["status"] == "degraded" else NODE_OK
        tr.record(
            "llm_fallback", status, (time.perf_counter() - t0) * 1000,
            f"状态 {fallback_report['status']}，填充 {len(fallback_report.get('filled_keys', []))} 项"
            + (f"，原因：{fallback_report.get('reason')}" if fallback_report.get("reason") else ""),
        )
    else:
        tr.record("llm_fallback", NODE_SKIPPED, 0.0, "未启用（默认关闭）")

    # ---- 节点 4：run_ruleset ×N（规则类失败 → 降级，不吞异常）----------------
    rule_results: Dict[str, Any] = {}
    failed_ids: List[str] = []
    for rid in ruleset_ids:
        t0 = time.perf_counter()
        try:
            rule_results[rid] = run_ruleset(card, load_ruleset(rid))
            stats = rule_results[rid].stats
            tr.record(
                f"run_ruleset:{rid}", NODE_OK, (time.perf_counter() - t0) * 1000,
                f"检查 {stats.get('checked', 0)}（不合规 {stats.get('fail', 0)}"
                f"/ 待人工 {stats.get('manual', 0)}）",
            )
        except Exception as exc:  # noqa: BLE001 —— 降级语义：记录异常详情而非中断
            failed_ids.append(rid)
            tr.record(
                f"run_ruleset:{rid}", NODE_DEGRADED, (time.perf_counter() - t0) * 1000,
                f"{type(exc).__name__}: {exc}（该规则集结果缺失）",
            )

    # ---- 节点 5：merge+diff -------------------------------------------------
    t0 = time.perf_counter()
    results = {
        rid: {"stats": res.stats, "findings": [asdict(f) for f in res.findings]}
        for rid, res in rule_results.items()
    }
    dual = None
    merge_detail = f"产出 {len(results)} 个规则集结果"
    if len(ruleset_ids) >= 2 and not (set(failed_ids) & {ruleset_ids[0], ruleset_ids[-1]}):
        dual = dual_diff(rule_results, ruleset_ids[0], ruleset_ids[-1])
        merge_detail += f"；dual_diff 新增不合规 {len(dual.get('new_fails', []))} 项"
    elif len(ruleset_ids) >= 2:
        merge_detail += f"；dual_diff 跳过（规则集 {failed_ids} 结果缺失）"
    tr.record(
        "merge_diff", NODE_DEGRADED if failed_ids else NODE_OK,
        (time.perf_counter() - t0) * 1000, merge_detail,
    )

    # ---- 节点 6：emit -------------------------------------------------------
    t0 = time.perf_counter()
    out: Dict[str, Any] = {
        "engine_version": __version__,
        "ruleset_ids": list(ruleset_ids),
        "card": card.to_dict(),
        "fallback": fallback_report,
        "results": results,
    }
    if dual is not None:
        out["dual_diff"] = dual
    tr.record("emit", NODE_OK, (time.perf_counter() - t0) * 1000, "结果 JSON 组装完成")
    out["pipeline"] = {"nodes": tr.nodes}
    out["warnings"] = tr.warnings
    return out


def check_text(text: str, ruleset_ids: List[str], llm_config=None) -> Dict[str, Any]:
    """对一段标签文本执行完整审查（内存文本入口，契约与 M4 一致）。

    llm_config 为 None 或 enabled=False 时完全不感知 LLM（核心通路零 API）。
    """
    return run_pipeline(text=text, ruleset_ids=ruleset_ids, llm_config=llm_config)


def parse_text(text: str) -> Dict[str, Any]:
    """仅解析为参数卡（flcheck parse 子命令）。"""
    return parse_label(text).to_dict()
