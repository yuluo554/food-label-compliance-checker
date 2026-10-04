"""V1–V8 违规注入器：变异 LabelState 并落真值条目（主期望 + also_expect）。

每个注入器返回 1..n 条真值条目 {type, main_expect, also_expect, detail}：
- V1 删多个字段 → 每字段一条条目（各自 main_expect）；
- 其余类型各 1 条。
适用性：先按模板 v_supported 过滤，apply 前再按运行时状态复查（如 V7 需要
生产日期未被 V1 删除）。注入顺序按 V1→V8 固定执行，保证确定性。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from .nutrients import nrv_value
from .templates import LabelState

# V1 可删字段池：字段键 → (强制标示规则契约 id, 标签用语)。M3 规则库必须包含这些 MAND-* id。
DELETABLE_FIELDS: Dict[str, Dict[str, str]] = {
    "food_name": {"rule_id": "MAND-NAME-01", "label": "食品名称"},
    "ingredients": {"rule_id": "MAND-ING-01", "label": "配料"},
    "net_content": {"rule_id": "MAND-NET-01", "label": "净含量"},
    "shelf_life": {"rule_id": "MAND-SHELF-01", "label": "保质期"},
    "production_date": {"rule_id": "MAND-DATE-01", "label": "生产日期"},
    "storage_conditions": {"rule_id": "MAND-STORAGE-01", "label": "贮存条件"},
    "sc_license": {"rule_id": "MAND-SC-01", "label": "食品生产许可证编号"},
}

# V4 营养声称（阈值超限方向）；阈值语义挂 GB 28050 待核对
V4_CLAIM = "无糖"
# V5 受限声称（2025 版限制"零添加/不添加"，2011 无对应规则 → 双标尺差异）
V5_CLAIMS = ("零添加防腐剂", "零添加甜味剂", "不添加防腐剂")
# V8 功能声称白名单外（疾病治疗/预防类声称，任何版本均不允许）
V8_CLAIMS = ("降血糖", "防癌抗癌", "治疗便秘", "消炎抑菌")
# V7a 非规范日期格式模板（{y}{m}{d} 未补零/紧凑式；规范格式为 YYYY年MM月DD日）
V7A_FORMATS = ("dot", "compact", "slash")
# V3 能量相对偏差（比例式：shown = round(correct × (1+f))）。
# 方向依据 GB 28050 表2（2011 §6.4 / 2025 §6.7，已核对）：能量"实际值 ≤120% 标示值"，
# 只约束低报方向 → 全部取负值（低报）；|f| ≥ 0.25 时 实际/标示 ≥ 1/0.75 > 1.2，
# 同时超出两版允许误差与任何合理的内部折算容差
V3_FACTORS = (-0.5, -0.4, -0.35, -0.25)
# V2 NRV% 偏差幅度（百分点，超出 ±1 修约间隔；两版 A.2/A.3.2 已核对）
V2_DEVIATIONS = (3, 4, 5, 6, 8)
# V7b 到期日偏移天数（正=晚于真实到期，负=早于）
V7B_SHIFTS = (-45, -30, -20, -10, 10, 20, 30, 45)

V_ORDER = ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8")


def _entry(vtype: str, rule_id: str, detail: Dict[str, Any], also: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": vtype,
        "main_expect": {"rule_id": rule_id, "level": "不合规"},
        "also_expect": also,
        "detail": detail,
    }


def applicable(state: LabelState, vtype: str) -> bool:
    """运行时适用性：模板支持 + 前置状态未被其他注入破坏。"""
    if vtype not in state.template.v_supported:
        return False
    if vtype == "V1":
        return any(k not in state.deleted for k in DELETABLE_FIELDS)
    if vtype == "V6":
        return state.template.over2_prefix >= 2
    if vtype == "V7":
        return "production_date" not in state.deleted and "shelf_life" not in state.deleted
    if vtype == "V2":
        return any(r["nrv_percent"] is not None for r in state.nutrition)
    if vtype == "V4":
        return any(r["name"] == "糖" for r in state.nutrition)
    return True


def apply(state: LabelState, rng, vtype: str) -> List[Dict[str, Any]]:
    """执行注入并返回真值条目。rng 为该样本专属 random.Random。"""
    if vtype == "V1":
        return _inject_v1(state, rng)
    if vtype == "V2":
        return [_inject_v2(state, rng)]
    if vtype == "V3":
        return [_inject_v3(state, rng)]
    if vtype == "V4":
        return [_inject_v4(state, rng)]
    if vtype == "V5":
        return [_inject_v5(state, rng)]
    if vtype == "V6":
        return [_inject_v6(state, rng)]
    if vtype == "V7":
        return [_inject_v7(state, rng)]
    if vtype == "V8":
        return [_inject_v8(state, rng)]
    raise ValueError(f"未知注入类型：{vtype}")


def _inject_v1(state: LabelState, rng) -> List[Dict[str, Any]]:
    candidates = [k for k in DELETABLE_FIELDS if k not in state.deleted]
    count = rng.randint(1, min(3, len(candidates)))
    # 自实现选择：洗牌后取前 count（不使用 random.sample，规避跨版本实现漂移）
    pool = list(candidates)
    for i in range(len(pool) - 1, 0, -1):
        j = rng.randrange(i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    entries: List[Dict[str, Any]] = []
    for key in sorted(pool[:count]):
        state.deleted.add(key)
        meta = DELETABLE_FIELDS[key]
        entries.append(
            _entry(
                "V1",
                meta["rule_id"],
                {"deleted_field": key, "deleted_label": meta["label"]},
                [],
            )
        )
    return entries


def _nutrition_row(state: LabelState, name: str) -> Dict[str, Any]:
    for row in state.nutrition:
        if row["name"] == name:
            return row
    raise KeyError(name)


def _inject_v2(state: LabelState, rng) -> Dict[str, Any]:
    rows = [r for r in state.nutrition if r["nrv_percent"] is not None]
    row = rows[rng.randrange(len(rows))]
    correct = int(row["nrv_percent"])
    dev = V2_DEVIATIONS[rng.randrange(len(V2_DEVIATIONS))]
    if rng.random() < 0.5:
        dev = -dev
    shown = correct + dev
    if shown < 0:  # 负向越界翻为正向，保证实际偏差恒 ≥3 个百分点
        shown = correct + abs(dev)
    row["nrv_percent"] = shown
    return _entry(
        "V2",
        "NRV-RECALC-01",
        {"row": row["name"], "shown_nrv_percent": shown, "recomputed_nrv_percent": correct},
        [{"kind": "info", "note": "NRV% 行级结论挂在被改写行上"}],
    )


def _inject_v3(state: LabelState, rng) -> Dict[str, Any]:
    row = _nutrition_row(state, "能量")
    correct = int(row["amount"])
    factor = V3_FACTORS[rng.randrange(len(V3_FACTORS))]
    shown = round(correct * (1 + factor))
    if shown == correct:  # 理论不可达（|f|≥0.2），防御性兜底
        shown = correct + max(1, round(correct * 0.25))
    row["amount"] = shown
    # NRV% 单元格跟随错误能量重算（模拟制表者把折算错误带进全表），
    # 使 V3 精确只挂 ENERGY-CONSIST-01，不隐含 NRV-RECALC 结论
    row["nrv_percent"] = round(nrv_value("能量", float(shown), "kJ") * 100)
    return _entry(
        "V3",
        "ENERGY-CONSIST-01",
        {
            "shown_energy_kj": shown,
            "recomputed_energy_kj": correct,
            "shown_nrv_percent": row["nrv_percent"],
        },
        [],
    )


def _inject_v4(state: LabelState, rng) -> Dict[str, Any]:
    sugar = _nutrition_row(state, "糖")
    state.claims.append(V4_CLAIM)
    return _entry(
        "V4",
        "CLAIM-THRESH-01",
        {"claim": V4_CLAIM, "sugar_row_value": f"{sugar['amount']:g}g/100g(mL)"},
        [{"kind": "info", "note": "无糖阈值 ≤0.5g/100g(mL)，2011 表C.1 / 2025 表C.1 已核对"}],
    )


def _inject_v5(state: LabelState, rng) -> Dict[str, Any]:
    claim = V5_CLAIMS[rng.randrange(len(V5_CLAIMS))]
    state.claims.append(claim)
    return _entry(
        "V5",
        "CLAIM-ZEROADD-01",
        {"claim": claim},
        [
            {"absent_in_ruleset": "gb7718-2011", "rule_id": "CLAIM-ZEROADD-01"},
            {"present_in_ruleset": "gb7718-2025", "rule_id": "CLAIM-ZEROADD-01"},
        ],
    )


def _inject_v6(state: LabelState, rng) -> Dict[str, Any]:
    k = state.template.over2_prefix
    idx = rng.randrange(k - 1)
    a, b = state.ingredients[idx], state.ingredients[idx + 1]
    state.ingredients[idx], state.ingredients[idx + 1] = b, a
    return _entry(
        "V6",
        "ING-ORDER-01",
        {"swapped": [a, b], "position": idx},
        [{"kind": "info", "note": "互换双方占比均 >2%，不适用 ≤2% 例外"}],
    )


def _inject_v7(state: LabelState, rng) -> Dict[str, Any]:
    if rng.random() < 0.5:
        d = state.production_date
        kind = V7A_FORMATS[rng.randrange(len(V7A_FORMATS))]
        if kind == "dot":
            shown = f"{d.year}.{d.month}.{d.day}"
        elif kind == "compact":
            shown = f"{d.year}{d.month:02d}{d.day:02d}"
        else:
            shown = f"{d.year}/{d.month}/{d.day}"
        state.nonstandard_date = shown
        return _entry(
            "V7",
            "FMT-DATE-01",
            {"variant": "format", "shown": shown, "correct": d.strftime("%Y年%m月%d日")},
            [],
        )
    shift = V7B_SHIFTS[rng.randrange(len(V7B_SHIFTS))]
    shown = date.fromordinal(state.expiry_date.toordinal() + shift)
    state.shown_expiry_date = shown
    return _entry(
        "V7",
        "DATE-LOGIC-01",
        {
            "variant": "logic",
            "shown_expiry": shown.strftime("%Y年%m月%d日"),
            "correct_expiry": state.expiry_date.strftime("%Y年%m月%d日"),
            "shift_days": shift,
        },
        [],
    )


def _inject_v8(state: LabelState, rng) -> Dict[str, Any]:
    claim = V8_CLAIMS[rng.randrange(len(V8_CLAIMS))]
    state.claims.append(claim)
    return _entry(
        "V8",
        "CLAIM-FUNC-01",
        {"claim": claim},
        [{"kind": "info",
          "note": "白名单外：2011 附录D（D.2–D.24）/ 2025 附录D 为营养素作用声称标准用语，已核对；所选拼写均为疾病类声称，任何版本均不允许"}],
    )
