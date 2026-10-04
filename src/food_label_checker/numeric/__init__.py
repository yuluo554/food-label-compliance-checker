"""数值复算引擎（M3，plan/04 §3）：纯确定性计算，数值结论不经过 LLM。

基准值与系数唯一出处 rules/nutrient_reference.json（status=已核对，挂 GB 28050
条款出处与条文块 quote_ref）。复算口径与生成器共用同一实现，保证干净样本
零误报、注入样本按真值命中：

- NRV%：round(amount / NRV × 100)，修约间隔 1（2011 A.2 / 2025 A.3.2，已核对；
  round 为五成双，与 datagen.templates.build_nutrition_rows 同一路径）；行级
  偏差 |标示-复算| > 1 判不一致（±1 容纳修约方式差异，plan/04 §3）；
- 能量：E = round(17×蛋白 + 37×脂肪 + 17×碳水)（GB 28050-2025 §2.3 原文；
  2011 版无对应条款，挂 2025 出处，D20）；允许误差按表2（2011 §6.4 /
  2025 §6.7，两版一致）"实际值 ≤120% 标示值"——只约束低报方向：复算值
  超过标示值的 120% 判矛盾，另留 ±1 kJ 修约容差（D16：干净样本能量即
  round 折算值）；
- 声称阈值：无糖 ≤0.5g/100g(mL)、低糖 ≤5、低钠 ≤120mg（两版表C.1，已核对），
  阈值表读 nutrient_reference.claim_thresholds；声称了对应成分但营养成分表
  无该行（或行为每份标示）时无法复算，由引擎转"待人工确认"；
- 日期逻辑：保质期到期日 = 生产日期 + 保质期（月单位月加法且日截断到月末、
  天单位按天加法）——共用 datagen.templates.add_months/compute_expiry，不得
  另写一套（生成器约定口径，D16；GB 未明文规定到期日推算方法）。

数值合法性前置（plan/04 §3）：成分含量为负数时该行不进复算（交引擎按
待人工确认处理）；本模块不做输入清洗，只对可计算形态负责。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from ..datagen.nutrients import energy_factors, nrv_table
from ..datagen.templates import compute_expiry

# NRV% / 能量复算的修约容差（修约间隔 1 的两倍口径内不算矛盾；见模块注释）
NRV_TOLERANCE = 1
ENERGY_TOLERANCE_KJ = 1
# 表2 允许误差上限：能量实际值 ≤120% 标示值（两版一致，已核对）
ENERGY_ALLOWED_RATIO = 1.2


def _row(card, name: str) -> Optional[Dict[str, Any]]:
    for row in card.nutrition_table:
        if row.get("name") == name:
            return row
    return None


def recompute_nrv_percent(name: str, amount: float, unit: str) -> Optional[int]:
    """单行 NRV% 复算：round(amount/NRV×100)；无 NRV 基准或单位不符返回 None。"""
    entry = nrv_table().get(name)
    if entry is None or entry.get("unit") != unit:
        return None
    return round(amount / float(entry["value"]) * 100)


def check_nrv_rows(card) -> List[Dict[str, Any]]:
    """逐行复算 NRV%：返回不一致行列表 [{name, shown, recomputed, diff}]。

    跳过：无 NRV% 标示的行（糖等，横线/空白）、per_serving 行（无每份基准
    无法复算）、NRV 表外营养素、负含量行（非法值交人工）。
    """
    mismatches: List[Dict[str, Any]] = []
    for row in card.nutrition_table:
        shown = row.get("nrv_percent")
        if shown is None or row.get("per_serving"):
            continue
        amount = row.get("amount")
        if not isinstance(amount, (int, float)) or amount < 0:
            continue
        recomputed = recompute_nrv_percent(
            row.get("name", ""), float(amount), row.get("unit", "")
        )
        if recomputed is None:
            continue
        diff = float(shown) - recomputed
        if abs(diff) > NRV_TOLERANCE:
            mismatches.append(
                {
                    "name": row.get("name", ""),
                    "shown": shown,
                    "recomputed": recomputed,
                    "diff": diff,
                    "evidence": row.get("evidence"),
                }
            )
    return mismatches


def recompute_energy(protein: float, fat: float, carb: float) -> int:
    """能量折算：round(17P+37F+17C)（系数挂 GB 28050-2025 §2.3，D20）。"""
    f = energy_factors()
    return round(f["蛋白质"] * protein + f["脂肪"] * fat + f["碳水化合物"] * carb)


def check_energy_consistency(card) -> Optional[Dict[str, Any]]:
    """能量折算一致性三态：violation（低报超表2 容差）/ ok / None（不可复算）。

    需要 能量/蛋白质/脂肪/碳水化合物 四行齐全且非 per_serving、单位为
    kJ/g 量纲；任一不满足返回 None（引擎按 not_run/待人工确认处理）。
    低报判定：复算值 > 120% × 标示值 + 1 kJ（表2 方向 + 修约容差）。
    """
    energy = _row(card, "能量")
    protein = _row(card, "蛋白质")
    fat = _row(card, "脂肪")
    carb = _row(card, "碳水化合物")
    rows = [energy, protein, fat, carb]
    if any(r is None or r.get("per_serving") for r in rows):
        return None
    if energy.get("unit") != "kJ" or any(r.get("unit") != "g" for r in rows[1:]):
        return None
    amounts = [r.get("amount") for r in rows]
    if any(not isinstance(a, (int, float)) or a < 0 for a in amounts):
        return None
    shown = float(amounts[0])
    recomputed = recompute_energy(float(amounts[1]), float(amounts[2]), float(amounts[3]))
    if recomputed > ENERGY_ALLOWED_RATIO * shown + ENERGY_TOLERANCE_KJ:
        return {
            "verdict": "violation",
            "shown_energy_kj": amounts[0],
            "recomputed_energy_kj": recomputed,
            "allowed_ratio": ENERGY_ALLOWED_RATIO,
            "evidence": energy.get("evidence"),
        }
    return {
        "verdict": "ok",
        "shown_energy_kj": amounts[0],
        "recomputed_energy_kj": recomputed,
        "evidence": energy.get("evidence"),
    }


def claim_threshold_checks(card) -> List[Dict[str, Any]]:
    """声称阈值核验：对每条声称×每个已核对阈值给出可判定结论。

    verdict：pass（含量达阈值）/ fail（超阈值）/ no_row（营养成分表缺该行，
    无法复算）/ per_serving（每份标示无法按每100g(mL) 复算）。
    """
    from ..datagen.nutrients import load_nutrient_reference

    thresholds = load_nutrient_reference().get("claim_thresholds", [])
    results: List[Dict[str, Any]] = []
    for claim in card.claims:
        for th in thresholds:
            if th.get("claim_contains") not in claim:
                continue
            row = _row(card, th["nutrient"])
            entry = {
                "claim": claim,
                "claim_contains": th["claim_contains"],
                "nutrient": th["nutrient"],
                "max_per_100": th["max_per_100"],
                "unit": th["unit"],
                "amount": None,
                "verdict": "no_row",
                "evidence": None,
            }
            if row is not None:
                entry["evidence"] = row.get("evidence")
                if row.get("per_serving"):
                    entry["verdict"] = "per_serving"
                else:
                    amount = row.get("amount")
                    if isinstance(amount, (int, float)) and amount >= 0:
                        entry["amount"] = amount
                        entry["verdict"] = (
                            "pass" if float(amount) <= float(th["max_per_100"]) else "fail"
                        )
            results.append(entry)
    return results


def compute_expected_expiry(production_iso: str, shelf_value: Any, shelf_unit: str) -> date:
    """按生成器约定推算到期日（共用 templates.compute_expiry，D16）。

    shelf_unit 仅支持 个月/天（解析层已归一）；其他单位抛 ValueError 由
    引擎转"待人工确认"。
    """
    prod = date.fromisoformat(production_iso)
    return compute_expiry(prod, int(shelf_value), shelf_unit)
