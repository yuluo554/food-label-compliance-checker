"""文本标签解析器。

M0 骨架：仅实现食品名称 / 净含量 / 生产日期三个字段示范"规则优先解析 +
证据逐字摘录"通路，字段全量实现见里程碑 M2（plan/05）。
"""
from __future__ import annotations

import re

from ..models import Evidence, LabelCard, LabelField

NAME_RE = re.compile(r"食品名称\s*[：:]\s*(?P<value>\S.*)")
NET_RE = re.compile(
    r"净含量\s*[：:]?\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>毫升|mL|ml|克|g|升|L)"
)
DATE_RE = re.compile(
    r"生产日期\s*[：:]?\s*(?P<value>\d{4}\s*[年./\-]\s*\d{1,2}\s*[月./\-]\s*\d{1,2}\s*日?)"
)

# 已被上面正则覆盖的行前缀，不再进 unresolved 提示
_PARSED_PREFIXES = ("食品名称", "净含量", "生产日期")
# 骨架阶段暂不解析、但明显有内容的行，提示给 M2（喂给 LLM 兜底/待人工）
_UNRESOLVED_HINTS = (
    "配料",
    "保质期",
    "到期日",
    "贮存",
    "营养成分",
    "致敏",
    "生产商",
    "生产者",
    "许可证",
    "标准代号",
    "质量等级",
)


def parse_label(text: str) -> LabelCard:
    """把文本标签解析为标签参数卡（骨架版）。"""
    card = LabelCard()

    m = NAME_RE.search(text)
    if m:
        card.fields["food_name"] = LabelField(
            key="food_name",
            value=m.group("value").strip(),
            evidence=Evidence(region="名称栏", quote=m.group(0).strip(), span=m.span()),
        )
    else:
        card.unresolved.append("食品名称：未检出『食品名称：』标示行")

    m = NET_RE.search(text)
    if m:
        unit = m.group("unit")
        card.fields["net_content"] = LabelField(
            key="net_content",
            value={"amount": float(m.group("amount")), "unit": unit},
            unit=unit,
            evidence=Evidence(region="净含量行", quote=m.group(0).strip(), span=m.span()),
        )
    else:
        card.unresolved.append("净含量：未检出『净含量：数值+单位』标示行")

    m = DATE_RE.search(text)
    if m:
        card.fields["production_date"] = LabelField(
            key="production_date",
            value=m.group("value").replace(" ", ""),
            evidence=Evidence(region="日期栏", quote=m.group(0).strip(), span=m.span()),
        )
    else:
        card.unresolved.append("生产日期：未检出可解析的日期格式")

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(_PARSED_PREFIXES):
            continue
        if any(h in s for h in _UNRESOLVED_HINTS):
            card.unresolved.append(f"待 M2 解析：{s}")

    return card
