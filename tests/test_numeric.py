"""数值复算引擎单元测试（M3）：NRV% 复算、能量折算、声称阈值、日期逻辑。"""
from datetime import date

import pytest

from food_label_checker.datagen.nutrients import compute_energy
from food_label_checker.datagen.templates import add_months, compute_expiry
from food_label_checker.models import LabelCard, LabelField
from food_label_checker.numeric import (
    check_energy_consistency,
    check_nrv_rows,
    claim_threshold_checks,
    compute_expected_expiry,
    recompute_energy,
    recompute_nrv_percent,
)


def _card(rows=None, claims=None):
    card = LabelCard()
    card.nutrition_table = list(rows or [])
    card.claims = list(claims or [])
    return card


def _row(name, amount, unit, nrv=None, per_serving=False):
    return {"name": name, "amount": amount, "unit": unit,
            "nrv_percent": nrv, "per_serving": per_serving, "evidence": None}


# ---------------------------------------------------------------------------
# NRV% 复算（修约间隔 1，容差 ±1）
# ---------------------------------------------------------------------------

def test_recompute_nrv_percent_known_values():
    assert recompute_nrv_percent("蛋白质", 10.0, "g") == 17      # 16.67 → 17
    assert recompute_nrv_percent("能量", 1000, "kJ") == 12       # 11.90 → 12
    assert recompute_nrv_percent("钠", 580, "mg") == 29          # 29.0
    assert recompute_nrv_percent("糖", 10.5, "g") is None        # 糖无 NRV


def test_check_nrv_rows_tolerance_and_mismatch():
    rows = [_row("蛋白质", 10.0, "g", nrv=16), _row("钠", 580, "mg", nrv=30)]
    assert check_nrv_rows(_card(rows)) == []  # |16-17|=1、|30-29|=1 → 容差内
    rows[0]["nrv_percent"] = 8
    mismatch = check_nrv_rows(_card(rows))
    assert len(mismatch) == 1
    assert mismatch[0]["name"] == "蛋白质"
    assert mismatch[0]["recomputed"] == 17


def test_check_nrv_rows_skips_dash_and_per_serving():
    rows = [_row("糖", 10.5, "g", nrv=None), _row("钠", 580, "mg", nrv=99, per_serving=True)]
    assert check_nrv_rows(_card(rows)) == []


# ---------------------------------------------------------------------------
# 能量折算（17/37/17，表2 低报方向，±1 kJ 容差）
# ---------------------------------------------------------------------------

def test_recompute_energy_matches_generator():
    assert recompute_energy(2.8, 3.0, 12.0) == compute_energy(2.8, 3.0, 12.0)
    assert recompute_energy(0, 0, 0) == 0


def _full_table(shown_energy):
    return [
        _row("能量", shown_energy, "kJ", nrv=12),
        _row("蛋白质", 10.0, "g", nrv=17),
        _row("脂肪", 5.0, "g", nrv=8),
        _row("碳水化合物", 50.0, "g", nrv=17),
    ]


def test_energy_consistency_ok_and_low_report_violation():
    calc = recompute_energy(10.0, 5.0, 50.0)  # 170+185+850 = 1205
    ok = check_energy_consistency(_card(_full_table(calc)))
    assert ok["verdict"] == "ok"
    # 低报 40%：标示 723 → 实际/标示 = 1.667 > 1.2 → 违规
    bad = check_energy_consistency(_card(_full_table(723)))
    assert bad["verdict"] == "violation"
    assert bad["recomputed_energy_kj"] == calc


def test_energy_consistency_small_gap_within_tolerance():
    # 标示值比折算值低 1 kJ：在 ±1 kJ 修约容差内，不报（D16 口径）
    calc = recompute_energy(10.0, 5.0, 50.0)
    result = check_energy_consistency(_card(_full_table(calc - 1)))
    assert result["verdict"] == "ok"


def test_energy_consistency_not_computable_cases():
    assert check_energy_consistency(_card()) is None                      # 缺行
    assert check_energy_consistency(_card(_full_table(1205)[:3])) is None  # 缺碳水
    per_serving = _full_table(1205)
    per_serving[0]["per_serving"] = True
    assert check_energy_consistency(_card(per_serving)) is None           # 每份标示
    bad_unit = _full_table(1205)
    bad_unit[1]["unit"] = "mg"
    assert check_energy_consistency(_card(bad_unit)) is None              # 单位不符


# ---------------------------------------------------------------------------
# 声称阈值（无糖 ≤0.5 / 低糖 ≤5 / 低钠 ≤120，两版表C.1 已核对）
# ---------------------------------------------------------------------------

def test_claim_threshold_sugar_boundary():
    rows = [_row("糖", 0.5, "g"), _row("钠", 580, "mg")]
    checks = claim_threshold_checks(_card(rows, claims=["无糖"]))
    assert checks[0]["verdict"] == "pass"       # 0.5 ≤ 0.5 边界内
    rows[0]["amount"] = 0.6
    checks = claim_threshold_checks(_card(rows, claims=["无糖"]))
    assert checks[0]["verdict"] == "fail"


def test_claim_threshold_low_sodium_and_no_row():
    rows = [_row("钠", 100, "mg")]
    checks = claim_threshold_checks(_card(rows, claims=["低钠"]))
    assert checks[0]["verdict"] == "pass"
    checks = claim_threshold_checks(_card([], claims=["无糖"]))
    assert checks[0]["verdict"] == "no_row"


def test_claim_threshold_unrelated_claim_no_entry():
    assert claim_threshold_checks(_card([], claims=["零添加甜味剂"])) == []


# ---------------------------------------------------------------------------
# 日期逻辑（共用 datagen 口径：月加法日截断/天加法）
# ---------------------------------------------------------------------------

def test_month_add_truncates_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 9, 12), 10) == date(2027, 7, 12)
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)  # 闰年截断


def test_compute_expiry_day_unit():
    assert compute_expiry(date(2026, 9, 12), 21, "天") == date(2026, 10, 3)


def test_compute_expected_expiry_iso_and_error():
    assert compute_expected_expiry("2026-09-12", 6, "个月") == date(2027, 3, 12)
    with pytest.raises(ValueError):
        compute_expected_expiry("2026-09-12", 2, "年")
