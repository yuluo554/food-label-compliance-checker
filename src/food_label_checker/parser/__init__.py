"""解析层：文本标签 → 标签参数卡（规则优先，LLM 只兜底）。"""

from .text_parser import parse_label

__all__ = ["parse_label"]
