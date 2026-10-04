"""解析层评测助手（M2 自测口径；M4 bench parse 全量口径在此基础上定稿）。

真值只能来自生成器：参数卡期望值由 generate_dataset_with_states 返回的
LabelState 重建（build_expected 与 render_label 的渲染约定一一对应）。期望值
不能从语料文本反向提取——那与被测解析器构成循环论证。内存重建与冻结
fixtures 的位级一致性由 tests/test_datagen_repro.py 守门；解析输入一律读
冻结文件本身（只读，勿重生成，决策 D18）。

对账口径（M2 自测版）：
- 计量单位为「字段实例」：标量字段 1 个、营养行按行名 1 个、声称按条 1 个；
- TP=解析存在且值相等；FN=期望有而解析缺失；值不等记 FN+FP 各 1；
- 期望全集之外的解析键/营养行/声称记 FP；V1 删除字段若被解析出值同样落 FP；
- F1 = 2TP / (2TP + FP + FN)，DoD 门槛 ≥0.9（M4 全量口径定稿）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from food_label_checker.datagen import generate_dataset_with_states
from food_label_checker.parser import parse_label

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "data" / "generated" / "frozen" / "seed-2026-n12"


def num_eq(parsed: Any, expected: Any) -> bool:
    """数值相等（None 与 None 相等；数值按 float 比较，兼容 int/float 形态）。"""
    if parsed is None or expected is None:
        return parsed is None and expected is None
    return float(parsed) == float(expected)


def value_eq(parsed: Any, expected: Any) -> bool:
    """字段值相等：dict 逐键比较（数值键按 num_eq），其余直接相等。"""
    if isinstance(expected, dict):
        if not isinstance(parsed, dict):
            return False
        for key, exp in expected.items():
            got = parsed.get(key)
            if isinstance(exp, (int, float)) and not isinstance(exp, bool):
                if not num_eq(got, exp):
                    return False
            elif got != exp:
                return False
        return True
    return parsed == expected


def build_expected(state) -> Dict[str, Any]:
    """从 LabelState 重建期望参数卡值（与 templates.render_label 渲染约定一致）。"""
    t = state.template
    deleted = state.deleted
    expected: Dict[str, Any] = {
        # render_label 恒渲染的部分（不受 V1 删除影响）
        "producer_name": f"{t.producer}（虚构演示数据）",
        "producer_address": t.address,
        "producer_contact": t.phone,
        "product_standard": t.product_standard,
        "salt_oil_sugar_notice": True,
        "claims": list(state.claims),
        "nutrition_table": [
            {
                "name": row["name"],
                "amount": float(row["amount"]),
                "unit": row["unit"],
                "nrv_percent": row["nrv_percent"],
            }
            for row in state.nutrition
        ],
    }
    if "food_name" not in deleted:
        expected["food_name"] = f"{t.brand} {t.name}"
    if "ingredients" not in deleted:
        expected["ingredients"] = list(state.ingredients)
    if "net_content" not in deleted:
        expected["net_content"] = {"amount": float(t.net_amount), "unit": t.net_unit}
    if "production_date" not in deleted:
        expected["production_date"] = state.production_date.isoformat()
    if "shelf_life" not in deleted:
        expected["shelf_life"] = {"value": t.shelf_value, "unit": t.shelf_unit}
    if "expiry_date" not in deleted:
        shown = state.shown_expiry_date or state.expiry_date
        expected["expiry_date"] = shown.isoformat()
    if "storage_conditions" not in deleted:
        expected["storage_conditions"] = t.storage
    if "sc_license" not in deleted:
        expected["sc_license"] = t.sc_license
    return expected


def load_frozen_dataset(data_dir: Path = FROZEN_DIR) -> Tuple[Dict[str, Any], List[Any]]:
    """读冻结集 truth.json 并内存重建各样本 LabelState（按样本顺序对齐）。"""
    truth = json.loads((data_dir / "truth.json").read_text(encoding="utf-8"))
    _, _, states = generate_dataset_with_states(
        truth["seed"], truth["n"], truth["categories"]
    )
    assert len(states) == len(truth["samples"]), "内存重建与冻结集样本数不一致"
    return truth, states


def evaluate_frozen(parse_fn: Callable = parse_label, data_dir: Path = FROZEN_DIR):
    """对冻结集逐样本评测解析器，返回 (metrics, issues)。解析输入为冻结文件。"""
    truth, states = load_frozen_dataset(data_dir)

    tp = fp = fn = 0
    issues: List[str] = []
    for sample, state in zip(truth["samples"], states):
        text = (data_dir / sample["file"]).read_text(encoding="utf-8")
        card = parse_fn(text)
        expected = build_expected(state)
        sid = sample["sample_id"]

        for key, exp in expected.items():
            if key == "nutrition_table":
                continue  # 营养行单独按行名对账
            if key == "claims":
                for claim in exp:
                    if claim in card.claims:
                        tp += 1
                    else:
                        fn += 1
                        issues.append(f"{sid}.claims: 缺声称『{claim}』")
                for claim in card.claims:
                    if claim not in exp:
                        fp += 1
                        issues.append(f"{sid}.claims: 期望外的声称『{claim}』")
                continue
            fld = card.get(key)
            if fld is None:
                fn += 1
                issues.append(f"{sid}.{key}: 缺失（期望 {exp!r}）")
            elif value_eq(fld.value, exp):
                tp += 1
            else:
                fn += 1
                fp += 1
                issues.append(f"{sid}.{key}: 解析 {fld.value!r} != 期望 {exp!r}")

        exp_rows = {row["name"]: row for row in expected["nutrition_table"]}
        parsed_rows: Dict[str, Dict[str, Any]] = {}
        for row in card.nutrition_table:
            name = row.get("name")
            if name in parsed_rows:
                fp += 1
                issues.append(f"{sid}.nutrition.{name}: 重复行")
            parsed_rows[name] = row
        for name, exp_row in exp_rows.items():
            prow = parsed_rows.get(name)
            if prow is None:
                fn += 1
                issues.append(f"{sid}.nutrition.{name}: 行缺失")
            elif (
                num_eq(prow.get("amount"), exp_row["amount"])
                and prow.get("unit") == exp_row["unit"]
                and num_eq(prow.get("nrv_percent"), exp_row["nrv_percent"])
            ):
                tp += 1
            else:
                fn += 1
                fp += 1
                issues.append(
                    f"{sid}.nutrition.{name}: 解析 "
                    f"({prow.get('amount')!r},{prow.get('unit')!r},{prow.get('nrv_percent')!r})"
                    f" != 期望 ({exp_row['amount']!r},{exp_row['unit']!r},{exp_row['nrv_percent']!r})"
                )
        for name in parsed_rows:
            if name not in exp_rows:
                fp += 1
                issues.append(f"{sid}.nutrition.{name}: 期望外的行")

        for key in card.fields:  # 期望全集之外的键 = 误报
            if key not in expected:
                fp += 1
                issues.append(f"{sid}.{key}: 期望之外的键")

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    metrics = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "samples": len(truth["samples"]),
    }
    return metrics, issues
