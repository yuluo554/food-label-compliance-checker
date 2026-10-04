"""文本标签解析器（M2）：文本标签 → 标签参数卡。

覆盖 plan/04 §1.1 参数卡字段表全部 P0 字段：food_name / ingredients /
net_content / production_date / shelf_life / expiry_date / storage_conditions /
生产者三项（producer_name/producer_address/producer_contact）/ sc_license /
product_standard / nutrition_table / claims；增补 salt_oil_sugar_notice
（2025 版 §4.5 强制提示语的在位性，供 M3 规则门控）。

解析契约（与 datagen/__init__.py §6 语料格式约定对齐，M2 定稿见 plan/06 D19）：
- 行式解析：``键：值``（全角/半角冒号均可，别名见 _LINE_FIELDS），配料按
  顿号/逗号分隔；同一键多行时首个成功解析的行生效；
- 营养成分表：标题行「营养成分表」开表，制表符三列（项目/每100g(mL)/NRV%），
  「项目」表头行的第 2 列定基准（"每份"→行级 per_serving=True），NRV 单元格
  「—」→ None（糖等无 NRV 的营养素）；行级证据挂每行；
- 日期字段 value 一律为 ISO（YYYY-MM-DD），原样标示文本留在 evidence.quote——
  V7a 非规范日期（点/斜杠/连字符/紧凑 8 位）也必须解析出日期值，格式是否
  规范由 M3 FMT-DATE-01 判定，解析层不得升级为「缺生产日期」误报；
- 证据挂全：每个字段与营养行都带 Evidence（区域+逐字摘录+span），quote 必须
  是输入文本的逐字子串，span 与 quote 逐字节对应（防幻觉硬校验，测试锁定）；
- 单位归一：净含量 g/克→g、mL/毫升→mL、L/升→L、kg/千克→kg；保质期
  月/个月→个月、天/日→天；原样写法留在 evidence.quote；
- 缺失强制标示字段（plan/04 §1.1 强制标示列，含营养成分表——豁免情形交人工/
  规则判断）记 unresolved；保质期到期日/声称/提示语等在 2011 语义下可合法
  缺失的字段不进 unresolved，由规则层判定。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ..models import Evidence, LabelCard, LabelField

# ---------------------------------------------------------------------------
# 行字段别名表：key → 行首别名；匹配时按别名长度降序，防「保质期」吃掉
# 「保质期到期日」。别名后必须紧跟冒号（全角/半角）才认作字段行。
# ---------------------------------------------------------------------------
_LINE_FIELDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("food_name", ("食品名称",)),
    ("ingredients", ("配料表", "配料")),
    ("product_standard", ("产品标准代号", "产品标准号", "执行标准号", "执行标准")),
    ("net_content", ("净含量",)),
    ("production_date", ("生产日期", "包装日期", "灌装日期")),
    ("expiry_date", ("保质期到期日", "保质期至", "到期日")),
    ("shelf_life", ("保质期",)),
    ("storage_conditions", ("贮存条件", "贮存方法", "贮存")),
    ("producer_name", ("生产商", "生产者", "制造商")),
    ("producer_address", ("地址",)),
    ("producer_contact", ("联系方式", "联系电话", "电话")),
    ("sc_license", ("食品生产许可证编号", "生产许可证编号", "许可证编号")),
)

_ALIAS_REGEXES: List[Tuple[Any, str]] = [
    # 长别名优先（防前缀吞并），别名须紧跟冒号
    (re.compile(r"^\s*" + re.escape(alias) + r"\s*[：:](?P<rest>.*)$"), key)
    for alias, key in sorted(
        ((alias, key) for key, aliases in _LINE_FIELDS for alias in aliases),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
]

_FIELD_LABEL = {
    "food_name": "食品名称",
    "ingredients": "配料",
    "net_content": "净含量",
    "production_date": "生产日期",
    "expiry_date": "保质期到期日",
    "shelf_life": "保质期",
    "storage_conditions": "贮存条件",
    "producer_name": "生产商",
    "producer_address": "地址",
    "producer_contact": "联系方式",
    "sc_license": "食品生产许可证编号",
    "product_standard": "产品标准代号",
    "claims": "声称",
    "salt_oil_sugar_notice": "盐油糖提示语",
}

_FIELD_REGION = {
    "food_name": "名称栏",
    "ingredients": "配料表",
    "net_content": "净含量行",
    "production_date": "日期栏",
    "expiry_date": "日期栏",
    "shelf_life": "日期栏",
    "storage_conditions": "贮存栏",
    "producer_name": "生产者栏",
    "producer_address": "生产者栏",
    "producer_contact": "生产者栏",
    "sc_license": "许可证栏",
    "product_standard": "标准代号栏",
}

# plan/04 §1.1 强制标示列（P0）→ 缺失进 unresolved；expiry_date（2025 新增
# 语义）/product_standard（视情形）等可合法缺失，由规则层判定
_MANDATORY_KEYS = (
    "food_name",
    "ingredients",
    "net_content",
    "production_date",
    "shelf_life",
    "storage_conditions",
    "producer_name",
    "producer_address",
    "producer_contact",
    "sc_license",
)

# 值解析失败的 unresolved 提示（行在但结构化失败）
_VALUE_PARSE_FAILURE = {
    "net_content": "净含量：标示行存在但未能解析出『数值+单位』",
    "production_date": "生产日期：标示行存在但无法解析出日期值",
    "expiry_date": "保质期到期日：标示行存在但无法解析出日期值",
    "shelf_life": "保质期：标示行存在但未能解析出『数值+单位』",
}

# 非 P0 但已知语义的行前缀 → unresolved 提示（喂给后续里程碑，不静默丢弃）
_NON_P0_PREFIXES = ("致敏", "质量等级")

_TABLE_TITLE_RE = re.compile(r"^营养成分表")
_SALT_NOTICE_RE = re.compile(r"儿童青少年应避免过量摄入盐油糖。?")
_CLAIM_RE = re.compile(r"^\s*声称\s*[：:]\s*(?P<rest>.+?)\s*$")

_NET_RE = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>mL|毫升|ml|ML|千克|kg|Kg|升|L|l|克|g)"
    r"(?:\s*(?P<spec>\S.*))?$"
)
_NET_UNIT_CANON = {
    "mL": "mL", "ml": "mL", "ML": "mL", "毫升": "mL",
    "L": "L", "l": "L", "升": "L",
    "kg": "kg", "Kg": "kg", "千克": "kg",
    "g": "g", "克": "g",
}

_SHELF_RE = re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>个月|月|天|日|年)\s*$")
_SHELF_UNIT_CANON = {"个月": "个月", "月": "个月", "天": "天", "日": "天", "年": "年"}

_NUTRIENT_AMOUNT_RE = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>千焦|毫克|微克|kJ|KJ|kj|mg|µg|μg|ug|g|克)\s*$"
)
_NUTRIENT_UNIT_CANON = {
    "kJ": "kJ", "KJ": "kJ", "kj": "kJ", "千焦": "kJ",
    "g": "g", "克": "g",
    "mg": "mg", "毫克": "mg",
    "µg": "μg", "μg": "μg", "ug": "μg", "微克": "μg",
}

# 日期：规范中式 → 点/斜杠/连字符（V7a）→ 紧凑 8 位（V7a，前后不能还是数字）
_CN_DATE_RE = re.compile(r"(?P<y>\d{4})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日?")
_SYM_DATE_RE = re.compile(r"(?P<y>\d{4})\s*[./-]\s*(?P<m>\d{1,2})\s*[./-]\s*(?P<d>\d{1,2})")
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?!\d)")


def _iter_lines(text: str):
    """按行迭代，yield (行起始偏移, 行内容)；行内容不含换行，去 CRLF 的 \\r。

    span 一律以原文为坐标系：quote 由行内容切片得到，必为原文逐字子串。
    """
    start = 0
    for raw in text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        yield start, line
        start += len(raw) + 1


def _parse_date_with_span(text: str) -> Optional[Tuple[str, int, int]]:
    """标示日期文本 → (ISO 日期, 匹配起, 匹配止)；无法解析返回 None。"""
    for regex in (_CN_DATE_RE, _SYM_DATE_RE, _COMPACT_DATE_RE):
        m = regex.search(text)
        if m:
            try:
                iso = date(int(m.group("y")), int(m.group("m")), int(m.group("d"))).isoformat()
            except ValueError:  # 形如 2026年13月40日：值非法，按未解析处理
                return None
            return iso, m.start(), m.end()
    return None


def _int_if_integral(raw: float):
    return int(raw) if raw == int(raw) else raw


def _parse_nrv(cell: str) -> Optional[float]:
    """NRV 单元格 → 数值（整数化）或 None（「—」等不适用标示）。"""
    cell = cell.strip()
    if not cell or set(cell) <= {"—", "-", "‐", "–", "‑"}:
        return None
    m = re.search(r"\d+(?:\.\d+)?", cell)
    if not m:
        return None
    return _int_if_integral(float(m.group()))


def _rest_span(m, rest: str) -> Tuple[int, int]:
    """rest 去首尾空白后的行内相对区间（quote 精确指向值部分）。"""
    left = len(rest) - len(rest.lstrip())
    return m.start("rest") + left, m.start("rest") + len(rest.rstrip())


def _string_field(key: str, line: str, start: int, m) -> Optional[LabelField]:
    rest = m.group("rest")
    value = rest.strip()
    if not value:
        return None
    s, e = _rest_span(m, rest)
    return LabelField(
        key=key,
        value=value,
        evidence=Evidence(region=_FIELD_REGION[key], quote=line[s:e], span=(start + s, start + e)),
    )


def _build_field(key: str, line: str, start: int, m) -> Optional[LabelField]:
    """别名行匹配 → LabelField；值无法结构化时返回 None（调用方记 unresolved）。"""
    rest = m.group("rest")

    if key == "net_content":
        nm = _NET_RE.match(rest)
        if not nm:
            return None
        unit = _NET_UNIT_CANON[nm.group("unit")]
        value: Dict[str, Any] = {"amount": float(nm.group("amount")), "unit": unit}
        spec = (nm.group("spec") or "").strip()
        if spec:
            value["spec"] = spec
        s = m.start("rest") + nm.start("amount")
        e = m.start("rest") + nm.end("unit")
        return LabelField(
            key=key,
            value=value,
            unit=unit,
            evidence=Evidence(region=_FIELD_REGION[key], quote=line[s:e], span=(start + s, start + e)),
        )

    if key in ("production_date", "expiry_date"):
        parsed = _parse_date_with_span(rest)
        if not parsed:
            return None
        iso, s, e = parsed
        return LabelField(
            key=key,
            value=iso,
            evidence=Evidence(region=_FIELD_REGION[key], quote=rest[s:e], span=(start + m.start("rest") + s, start + m.start("rest") + e)),
        )

    if key == "shelf_life":
        sm = _SHELF_RE.match(rest)
        if not sm:
            return None
        unit = _SHELF_UNIT_CANON[sm.group("unit")]
        value = {"value": _int_if_integral(float(sm.group("value"))), "unit": unit}
        s = m.start("rest") + sm.start("value")
        e = m.start("rest") + sm.end("unit")
        return LabelField(
            key=key,
            value=value,
            unit=unit,
            evidence=Evidence(region=_FIELD_REGION[key], quote=line[s:e], span=(start + s, start + e)),
        )

    if key == "ingredients":
        value_full = rest.strip()
        if not value_full:
            return None
        items = [seg.strip() for seg in re.split(r"[、，,]", value_full)]
        items = [seg for seg in items if seg]
        if not items:
            return None
        s, e = _rest_span(m, rest)
        return LabelField(
            key=key,
            value=items,
            evidence=Evidence(region=_FIELD_REGION[key], quote=line[s:e], span=(start + s, start + e)),
        )

    return _string_field(key, line, start, m)


def _is_table_title(stripped: str) -> bool:
    if "：" in stripped or ":" in stripped:
        return False
    return stripped == "营养成分表" or stripped.startswith("营养成分表")


def _parse_nutrition_row(cells: List[str], per_serving: bool, start: int, line: str) -> Optional[Dict[str, Any]]:
    """制表符三列行 → 营养行 dict（行级证据内嵌）；解析失败返回 None。"""
    name = cells[0]
    am = _NUTRIENT_AMOUNT_RE.match(cells[1])
    if not name or not am:
        return None
    quote = line.rstrip()
    return {
        "name": name,
        "amount": _int_if_integral(float(am.group("amount"))),
        "unit": _NUTRIENT_UNIT_CANON[am.group("unit")],
        "nrv_percent": _parse_nrv(cells[2]),
        "per_serving": per_serving,
        "evidence": {"region": "营养成分表", "quote": quote, "span": (start, start + len(quote))},
    }


def parse_label(text: str) -> LabelCard:
    """把文本标签解析为标签参数卡（M2 全字段版）。"""
    card = LabelCard()
    seen = set()
    noted_failed = set()
    claims: List[str] = []
    claim_evidence: Optional[Evidence] = None
    in_table = False
    per_serving = False

    for start, line in _iter_lines(text):
        stripped = line.strip()
        if not stripped:
            continue

        if in_table and "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
            if cells and cells[0] == "项目":  # 表头行：第 2 列定基准
                per_serving = len(cells) > 1 and not cells[1].startswith("每100")
                continue
            row = _parse_nutrition_row(cells, per_serving, start, line) if len(cells) >= 3 else None
            if row is not None:
                card.nutrition_table.append(row)
                continue
            in_table = False  # 非表行（列数不足/数值不可析）→ 退表，落通用分支
            card.unresolved.append("营养成分表：存在无法解析的表行，其后按普通行处理")

        if in_table:  # 无制表符的行结束营养表（提示语/声称/字段行接续其后）
            in_table = False

        if _is_table_title(stripped):
            in_table = True
            per_serving = False
            continue

        matched = None
        for regex, key in _ALIAS_REGEXES:
            m = regex.match(line)
            if m:
                matched = (m, key)
                break
        if matched is not None:
            m, key = matched
            if key in card.fields:
                continue  # 首个成功解析的行生效
            fld = _build_field(key, line, start, m)
            if fld is not None:
                card.fields[key] = fld
                if key == "ingredients":  # 顶层镜像（引擎门控/规则便利访问）
                    card.ingredients = list(fld.value)
            elif key not in noted_failed:  # 失败行记一次提示，后续行仍可重试
                noted_failed.add(key)
                card.unresolved.append(
                    _VALUE_PARSE_FAILURE.get(
                        key, f"{_FIELD_LABEL[key]}：标示行存在但未能解析出结构化值"
                    )
                )
            continue

        cm = _CLAIM_RE.match(line)
        if cm:
            claim_text = cm.group("rest")
            claims.append(claim_text)
            if claim_evidence is None:
                claim_evidence = Evidence(
                    region="声称文字",
                    quote=claim_text,
                    span=(start + cm.start("rest"), start + cm.end("rest")),
                )
            continue

        nm = _SALT_NOTICE_RE.search(line)  # 在 line 上搜索，保证 span 坐标一致
        if nm and "salt_oil_sugar_notice" not in seen:
            seen.add("salt_oil_sugar_notice")
            card.fields["salt_oil_sugar_notice"] = LabelField(
                key="salt_oil_sugar_notice",
                value=True,
                evidence=Evidence(
                    region="营养成分表",
                    quote=nm.group(),
                    span=(start + nm.start(), start + nm.end()),
                ),
            )
            continue

        if stripped.startswith(_NON_P0_PREFIXES):
            card.unresolved.append(f"非 P0 字段待后续里程碑解析：{stripped}")

    # 强制标示字段缺失 → 显式 unresolved（不静默缺失）
    for key in _MANDATORY_KEYS:
        if key not in card.fields:
            card.unresolved.append(f"{_FIELD_LABEL[key]}：未检出『{_FIELD_LABEL[key]}：』标示行")
    if not card.nutrition_table:
        card.unresolved.append("营养成分表：未检出营养成分表（豁免情形需人工判断）")

    card.claims = claims
    if claims:
        card.fields["claims"] = LabelField(
            key="claims", value=list(claims), evidence=claim_evidence
        )
    return card
