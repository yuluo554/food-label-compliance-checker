"""LLM 兜底抽取：候选行压缩 → 结构化提示词 → 逐字摘录校验 → 回填参数卡。

防幻觉三闸（与 D19 证据纪律同源）：
1. LLM 返回的 quote 必须是输入原文的逐字子串（quote in text），否则拒绝；
2. 字段值尽量从校验通过的 quote 派生（日期/净含量/保质期用解析器同款正则
   从 quote 重新解析，不信任 LLM 改写的值）；
3. 抽取出的字段 confidence=0.7、evidence.region="LLM 兜底"、
   card.llm_assisted=True——报告与 Web 须标注 LLM 参与（plan/04 §5）。

降级语义（plan/04 §5 / HANDOFF-M4）：LLM 关闭 → 不运行；不可达/超时/配置
缺失/响应不可解析 → status="degraded"，unresolved 字段由规则层按既有语义
处理（present_unparsed → 待人工确认 / 行整体缺失 → 不合规），不吞结论、
不造结论。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from ..models import Evidence, LabelCard, LabelField
from .client import LLMUnavailable

# 兜底候选字段（key → 提示词字段说明）。只覆盖 P0 行字段；营养表/声称有
# 专用结构化通路，不走 LLM。
FALLBACK_KEYS: Tuple[Tuple[str, str], ...] = (
    ("food_name", "食品名称（行『食品名称：…』）"),
    ("ingredients", "配料表（行『配料：…』，顿号分隔）"),
    ("net_content", "净含量（数值+单位，如 250mL）"),
    ("production_date", "生产日期（原样标示，如 2026年09月12日）"),
    ("shelf_life", "保质期（数值+单位，如 6个月）"),
    ("expiry_date", "保质期到期日（原样标示）"),
    ("storage_conditions", "贮存条件"),
    ("producer_name", "生产商/生产者/制造商名称"),
    ("producer_address", "生产者地址（行『地址：…』）"),
    ("producer_contact", "联系方式/电话"),
    ("sc_license", "食品生产许可证编号（SC 开头）"),
    ("product_standard", "产品标准代号/执行标准"),
)

FALLBACK_CONFIDENCE = 0.7
_MAX_LINES = 80
_MAX_CHARS = 4000

_SYSTEM_PROMPT = (
    "你是预包装食品标签的信息抽取助手，只做字段定位与原文摘录，"
    "不做合规判断、不推断数值。硬性要求：\n"
    "1. 只输出一个 JSON 数组，不输出任何解释文字或代码块标记；\n"
    '2. 数组每项形如 {"key": 字段名, "found": true/false, '
    '"quote": 原文逐字摘录, "value": 字段值}；\n'
    "3. quote 必须是候选行文本中的逐字子串（原样复制，不得改写、补全、"
    "翻译或增删空格）；\n"
    "4. 候选行中找不到的字段 found=false，quote 为空字符串；\n"
    "5. 数值与日期照抄原文标示，不要换算或格式化。"
)


def candidate_lines(text: str, max_lines: int = _MAX_LINES, max_chars: int = _MAX_CHARS) -> str:
    """候选行压缩：去空行、限行数与总长——只给 LLM 有信息量的行，控 token。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[str] = []
    total = 0
    for ln in lines[:max_lines]:
        out.append(ln)
        total += len(ln) + 1
        if total >= max_chars:
            out[-1] = out[-1][: max(0, max_chars - (total - len(ln)))]
            out.append("[候选行已按长度截断]")
            break
    if len(lines) > max_lines:
        out.append(f"[候选行已截断，原始共 {len(lines)} 行]")
    return "\n".join(out)


def build_messages(candidate_text: str, keys: List[str]) -> List[Dict[str, str]]:
    spec = {key: dict(FALLBACK_KEYS)[key] for key in keys}
    user = (
        f"请从以下候选行中定位这些字段：{json.dumps(spec, ensure_ascii=False)}\n"
        f"候选行文本：\n{candidate_text}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _parse_llm_json(content: str) -> List[Dict[str, Any]]:
    """LLM 输出 → JSON 数组；容忍 ```json 围栏。非法结构抛 LLMUnavailable。"""
    cleaned = content.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"LLM 响应不可解析为 JSON：{exc}") from exc
    if not isinstance(data, list):
        raise LLMUnavailable("LLM 响应 JSON 不是数组")
    return [item for item in data if isinstance(item, dict)]


def _value_from_quote(key: str, quote: str, raw_value: Any):
    """从校验通过的 quote 派生结构化值（与解析器同款契约）；失败返回 None。"""
    from ..parser import text_parser as tp

    if key in ("production_date", "expiry_date"):
        parsed = tp._parse_date_with_span(quote)
        return parsed[0] if parsed else None
    if key == "net_content":
        nm = tp._NET_RE.match(quote)
        if not nm:
            return None
        value: Dict[str, Any] = {
            "amount": float(nm.group("amount")),
            "unit": tp._NET_UNIT_CANON[nm.group("unit")],
        }
        spec = (nm.group("spec") or "").strip()
        if spec:
            value["spec"] = spec
        return value
    if key == "shelf_life":
        sm = tp._SHELF_RE.match(quote)
        if not sm:
            return None
        return {
            "value": float(sm.group("value")),
            "unit": tp._SHELF_UNIT_CANON[sm.group("unit")],
        }
    if key == "ingredients":
        rest = re.split(r"[：:]", quote, maxsplit=1)[1] if re.match(r".*[：:]", quote) else quote
        items = [seg.strip() for seg in re.split(r"[、，,]", rest) if seg.strip()]
        return items or None
    # 字符串字段：优先取冒号后的值段，回退 LLM 给的 value
    parts = re.split(r"[：:]", quote, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()
    return str(raw_value).strip() if raw_value else None


def apply_fallback(card: LabelCard, text: str, client) -> Dict[str, Any]:
    """对参数卡缺失的 P0 字段执行 LLM 兜底抽取，返回可序列化的兜底报告。"""
    candidates = [key for key, _ in FALLBACK_KEYS if card.get(key) is None]
    if not candidates:
        return {"enabled": True, "status": "not_needed", "reason": None,
                "candidates": [], "filled_keys": [], "rejected": [],
                "llm_assisted": False}

    report: Dict[str, Any] = {"enabled": True, "reason": None,
                              "candidates": candidates,
                              "filled_keys": [], "rejected": [],
                              "llm_assisted": False}
    try:
        content = client.chat(build_messages(candidate_lines(text), candidates))
        items = _parse_llm_json(content)
    except LLMUnavailable as exc:
        report["status"] = "degraded"
        report["reason"] = str(exc)
        return report

    for item in items:
        key = item.get("key")
        if key not in candidates or key in card.fields:
            continue
        if not item.get("found"):
            continue
        quote = item.get("quote")
        if not isinstance(quote, str) or not quote or quote not in text:
            report["rejected"].append(
                {"key": key, "reason": "quote 非原文逐字子串（防幻觉拒绝）"}
            )
            continue
        value = _value_from_quote(key, quote, item.get("value"))
        if value is None:
            report["rejected"].append(
                {"key": key, "reason": "值无法按字段契约从 quote 结构化"}
            )
            continue
        start = text.index(quote)
        card.fields[key] = LabelField(
            key=key,
            value=value,
            evidence=Evidence(region="LLM 兜底", quote=quote,
                              span=(start, start + len(quote))),
            confidence=FALLBACK_CONFIDENCE,
        )
        card.unresolved_detail.pop(key, None)
        if key == "ingredients":  # 顶层镜像（与解析器同约定）
            card.ingredients = list(value)
        report["filled_keys"].append(key)

    report["status"] = "applied"
    report["llm_assisted"] = bool(report["filled_keys"])
    if report["llm_assisted"]:
        card.llm_assisted = True
    return report
