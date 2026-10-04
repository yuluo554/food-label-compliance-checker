"""端到端对账评测器（M4 自 tests/test_engine_m3.py 固化语义迁入；plan/04 §6）。

对账口径（D16 §4 真值语义，与 M3 回归测试等价，D21）：
- 按"全部非 pass（不合规）集合"对账，而非单点命中；"待人工确认"不参与；
- 覆盖集（规则集 r）= 真值 main_expect ∪ also_expect(present_in_ruleset=r)
  − also_expect(absent_in_ruleset=r)——absent_in 按字面对账：命中即记
  absent_in 违例（计入误报，如 V5 的 CLAIM-ZEROADD-01 不得在 2011 触发）；
- 检出：真值每个 main_expect.rule_id 至少在一个启用规则集的不合规集合出现；
- 误报：规则集 r 的不合规集合中未被覆盖集覆盖的 rule_id（clean_baseline
  样本的全部 fail 记误报——干净承诺为零不合规）；
- dual_diff 回归（D21）：注入样本 new_fails 仅 V5 产生 [CLAIM-ZEROADD-01]，
  resolved_fails 恒空。
- 合格线：误报 0、检出率 1.0、dual_diff 零违例（M3 已在冻结集锁定，
  plan/05 M4 DoD"误报 0，检出率达标"）。

评测输入一律读数据集目录的语料文件（只读，D18）；真值只来自 truth.json。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..models import LEVEL_FAIL, LEVEL_MANUAL
from ..parser import parse_label
from ..rules.engine import AVAILABLE_RULESETS, dual_diff, load_ruleset, run_ruleset

DEFAULT_BENCH_DATA = "data/generated/frozen/seed-2026-n12"


def load_bench_dataset(data_dir: Any) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """读数据集 truth.json 与各样本语料文件（文件名为真值 file 键）。"""
    path = Path(data_dir)
    truth = json.loads((path / "truth.json").read_text(encoding="utf-8"))
    texts = {
        s["file"]: (path / s["file"]).read_text(encoding="utf-8")
        for s in truth["samples"]
    }
    return truth, texts


def _fail_ids(result) -> set:
    return {f.rule_id for f in result.findings if f.level == LEVEL_FAIL}


def evaluate_e2e(
    data_dir: Any,
    ruleset_ids: Tuple[str, ...] = AVAILABLE_RULESETS,
) -> Tuple[Dict[str, Any], List[str]]:
    """对数据集逐样本做双标尺对账，返回 (metrics, issues)。"""
    truth, texts = load_bench_dataset(data_dir)
    rulesets = {rid: load_ruleset(rid) for rid in ruleset_ids}

    main_total = 0
    detected = 0
    missed: List[str] = []
    fail_instances = 0
    false_positives = 0
    clean_violations: List[str] = []
    absent_violations: List[str] = []
    dual_diff_violations: List[str] = []
    manual_count = 0
    issues: List[str] = []

    for sample in truth["samples"]:
        sid = sample["sample_id"]
        card = parse_label(texts[sample["file"]])
        results = {rid: run_ruleset(card, rulesets[rid]) for rid in ruleset_ids}
        fails = {rid: _fail_ids(res) for rid, res in results.items()}
        manual_count += sum(
            1 for res in results.values() for f in res.findings if f.level == LEVEL_MANUAL
        )

        if sample["clean_baseline"]:
            for rid in ruleset_ids:
                for rule_id in sorted(fails[rid]):
                    false_positives += 1
                    clean_violations.append(f"{sid}/{rid}:{rule_id}")
                    issues.append(f"{sid}/{rid}: clean_baseline 误报 {rule_id}")
            fail_instances += sum(len(fails[rid]) for rid in ruleset_ids)
            continue

        mains = [inj["main_expect"]["rule_id"] for inj in sample["injections"]]
        main_total += len(mains)
        absent: Dict[str, set] = {rid: set() for rid in ruleset_ids}
        present: Dict[str, set] = {rid: set() for rid in ruleset_ids}
        for inj in sample["injections"]:
            for extra in inj.get("also_expect", []):
                if extra.get("absent_in_ruleset") in absent:
                    absent[extra["absent_in_ruleset"]].add(extra["rule_id"])
                if extra.get("present_in_ruleset") in present:
                    present[extra["present_in_ruleset"]].add(extra["rule_id"])

        for rid in ruleset_ids:
            covered = (set(mains) | present[rid]) - absent[rid]
            uncovered = fails[rid] - covered
            fail_instances += len(fails[rid])
            false_positives += len(uncovered)
            for rule_id in sorted(uncovered):
                if rule_id in absent[rid]:
                    absent_violations.append(f"{sid}/{rid}:{rule_id}")
                    issues.append(
                        f"{sid}/{rid}: absent_in 违例 {rule_id}（真值要求该规则集不触发）"
                    )
                else:
                    issues.append(f"{sid}/{rid}: 误报 {rule_id}（真值未覆盖）")

        union_fails: set = set()
        for rid in ruleset_ids:
            union_fails |= fails[rid]
        for rule_id in mains:
            if rule_id in union_fails:
                detected += 1
            else:
                missed.append(f"{sid}:{rule_id}")
                issues.append(f"{sid}: 漏检 {rule_id}（两把标尺均未报不合规）")

        if len(ruleset_ids) >= 2 and "gb7718-2011" in rulesets and "gb7718-2025" in rulesets:
            diff = dual_diff(results, "gb7718-2011", "gb7718-2025")
            expected_new = ["CLAIM-ZEROADD-01"] if "CLAIM-ZEROADD-01" in mains else []
            if diff["new_fails"] != expected_new or diff["resolved_fails"]:
                dual_diff_violations.append(sid)
                issues.append(
                    f"{sid}: dual_diff 异常 new_fails={diff['new_fails']} "
                    f"resolved={diff['resolved_fails']}（期望 {expected_new}/[]）"
                )

    detection_rate = round(detected / main_total, 4) if main_total else 1.0
    precision_like = fail_instances - false_positives
    fp_rate = (
        round(false_positives / fail_instances, 4) if fail_instances else 0.0
    )
    metrics = {
        "samples": len(truth["samples"]),
        "clean_samples": sum(1 for s in truth["samples"] if s["clean_baseline"]),
        "injected_samples": sum(1 for s in truth["samples"] if not s["clean_baseline"]),
        "rulesets": list(ruleset_ids),
        "main_expect_total": main_total,
        "detected": detected,
        "detection_rate": detection_rate,
        "missed": missed,
        "fail_instances": fail_instances,
        "covered_instances": precision_like,
        "false_positives": false_positives,
        "false_positive_rate": fp_rate,
        "clean_baseline_violations": clean_violations,
        "absent_in_violations": absent_violations,
        "dual_diff_violations": dual_diff_violations,
        "manual_findings_info_only": manual_count,
    }
    return metrics, issues
