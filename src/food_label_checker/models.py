"""标签参数卡与结论数据模型（schema 详见 plan/04-模块详设.md §1）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# 结论三级判定（plan/04 §4）
LEVEL_PASS = "合规"
LEVEL_FAIL = "不合规"
LEVEL_MANUAL = "待人工确认"

_LEVEL_STAT = {LEVEL_PASS: "pass", LEVEL_FAIL: "fail", LEVEL_MANUAL: "manual"}


@dataclass
class Evidence:
    """证据。quote 必须是输入文本的逐字子串（解析层保证，测试锁定）。"""

    region: str
    quote: str
    span: Optional[Tuple[int, int]] = None


@dataclass
class LabelField:
    """参数卡单字段：键-值-单位-置信度-证据。"""

    key: str
    value: Any
    unit: Optional[str] = None
    confidence: float = 1.0
    evidence: Optional[Evidence] = None


@dataclass
class LabelCard:
    """标签参数卡：解析层与规则层之间的统一中间表示。"""

    fields: Dict[str, LabelField] = field(default_factory=dict)
    nutrition_table: List[Dict[str, Any]] = field(default_factory=list)
    ingredients: List[str] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    # M4：unresolved 的机器可读子集，key → "present_unparsed"（标示行存在但
    # 结构化解析失败）。规则层据此对"行在而值不可析"输出"待人工确认"而非
    # 不合规——与"行整体缺失"（V1 语义，不合规）区分；D19 契约的追加项。
    unresolved_detail: Dict[str, str] = field(default_factory=dict)
    # M4：LLM 兜底参与过字段抽取时置 True（数值结论仍全部来自确定性规则）。
    llm_assisted: bool = False

    def has(self, key: str) -> bool:
        return key in self.fields

    def get(self, key: str) -> Optional[LabelField]:
        return self.fields.get(key)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    """单条审查结论。basis.status != '已核对' 时 flagged_pending_basis 必须为 True。"""

    rule_id: str
    level: str
    message: str
    ruleset_id: str
    basis: Dict[str, Any] = field(default_factory=dict)
    evidence: Optional[Evidence] = None
    advice: str = ""
    flagged_pending_basis: bool = False


@dataclass
class RuleResult:
    """单个规则集的审查结果与统计。"""

    ruleset_id: str
    findings: List[Finding] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
