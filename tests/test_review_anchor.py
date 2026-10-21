"""复核锚守门（D6 / D11）：开放项的"本次核对日期 / 下次复核日期"必须存在且合法。

背景：`nutrient_reference.json` 的 `rounding.status="已核对"` 曾被理解为覆盖
GB/T 8170 总则，而 `general_rule` 又写"条款未单独核对"——自相矛盾（D6）。修法
是给 `rounding` / `source` 两个对象挂显式复核锚，并让 `status_scope` 说清
`status` 的覆盖范围，同时把开放项写成 `open_item`。

本测试守住的是"复核锚不会悄悄消失"：日期必须能在今天之后被某个人读懂并触发
复核，而不是永远停在一个没写日期的 ✅ 上。逾期只打印提示，**不改退出码**——
日期过期是日程问题，不是代码缺陷，不应该让全量测试变红。
"""
import datetime as _dt
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NUTRIENT_REF = (
    REPO_ROOT / "src" / "food_label_checker" / "rules" / "nutrient_reference.json"
)

# 必须带复核锚的对象（D6/D11 的落点）
ANCHORED_OBJECTS = ("rounding", "source")


def _load():
    with open(NUTRIENT_REF, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_iso(value, where):
    assert isinstance(value, str) and value, f"{where} 必须是非空字符串，实际 {value!r}"
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:  # pragma: no cover - 失败时给出可读信息
        raise AssertionError(f"{where}={value!r} 不是合法 ISO 日期（YYYY-MM-DD）")


def test_review_anchors_present_and_valid():
    """rounding / source 两个对象都必须有合法 reviewed_at 与 next_review。"""
    data = _load()
    for key in ANCHORED_OBJECTS:
        assert key in data, f"nutrient_reference.json 缺 {key} 对象"
        obj = data[key]
        assert "reviewed_at" in obj, f"{key} 缺 reviewed_at（复核锚）"
        assert "next_review" in obj, f"{key} 缺 next_review（复核锚）"
        reviewed = _parse_iso(obj["reviewed_at"], f"{key}.reviewed_at")
        nxt = _parse_iso(obj["next_review"], f"{key}.next_review")
        assert nxt > reviewed, (
            f"{key}.next_review({nxt}) 必须晚于 reviewed_at({reviewed})"
        )


def test_rounding_status_scope_resolves_contradiction():
    """rounding 的 status=已核对 必须有 status_scope 限定范围，并列出 open_item。

    D6 的本质不是"某个字段写错了"，而是"status 的覆盖范围没写"：读者无法判断
    `已核对` 是覆盖 NRV% 修约间隔，还是也覆盖 general_rule 提到的 GB/T 8170。
    """
    rounding = _load()["rounding"]
    assert rounding.get("status") == "已核对"
    scope = rounding.get("status_scope")
    assert isinstance(scope, str) and scope.strip(), (
        "rounding.status_scope 缺失或为空——status=已核对 必须声明覆盖范围（D6）"
    )
    assert "8170" in scope, (
        f"rounding.status_scope 必须显式排除 GB/T 8170 总则，实际 {scope!r}"
    )
    open_item = rounding.get("open_item")
    assert isinstance(open_item, str) and open_item.strip(), (
        "rounding.open_item 缺失或为空——未核对的开放项必须显式登记（D6）"
    )
    # general_rule 仍须保留"未单独核对"这个事实，不能被改写成"已全部核对"
    assert "未单独核对" in rounding.get("general_rule", "")


def test_review_anchor_not_yet_due_is_informational():
    """逾期只提示不改退出码（日程问题不是代码缺陷）。

    这条测试永远通过，它存在的意义是把"下一次复核日期已过"写进 CI 日志。
    """
    today = _dt.date.today()
    due = []
    for key in ANCHORED_OBJECTS:
        nxt = _dt.date.fromisoformat(_load()[key]["next_review"])
        if nxt <= today:
            due.append(f"{key} 下次复核 {nxt} 已到期")
    if due:
        print("\n[review-anchor] 提示（不影响退出码）：" + "；".join(due))
