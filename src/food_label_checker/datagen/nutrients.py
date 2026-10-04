"""datagen 数值来源：NRV 基准值与能量系数（唯一出处 rules/nutrient_reference.json，status=待核对）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

NUTRIENT_REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent / "rules" / "nutrient_reference.json"
)


def load_nutrient_reference() -> Dict[str, Any]:
    if not NUTRIENT_REFERENCE_PATH.exists():
        raise FileNotFoundError(f"营养参考表缺失：{NUTRIENT_REFERENCE_PATH}")
    return json.loads(NUTRIENT_REFERENCE_PATH.read_text(encoding="utf-8"))


def nrv_table() -> Dict[str, Dict[str, Any]]:
    ref = load_nutrient_reference()
    return ref["nrv"]


def energy_factors() -> Dict[str, float]:
    ref = load_nutrient_reference()
    return ref["energy_factors_kj_per_g"]


def nrv_value(nutrient: str, amount: float, unit: str) -> float:
    """按含量与单位折算 NRV 分子分母可比值：amount(unit) / NRV(unit)。

    仅支持与 NRV 表相同的单位量纲（kJ/g/mg）；生成器模板保证。
    """
    entry = nrv_table()[nutrient]
    if entry["unit"] != unit:
        raise ValueError(f"单位不匹配：{nutrient} NRV 单位 {entry['unit']}，收到 {unit}")
    return amount / float(entry["value"])


def compute_energy(protein: float, fat: float, carb: float) -> int:
    """能量折算：round(17P+37F+17C)。

    系数已核对（GB 28050-2025 §2.3：蛋白质 17、脂肪 37、碳水化合物 17 kJ/g；
    2011 版条款出处 M3 补录）。五成双修约，NRV% 修约间隔 1（两版附录A 已核对）。
    """
    f = energy_factors()
    return round(f["蛋白质"] * protein + f["脂肪"] * fat + f["碳水化合物"] * carb)
