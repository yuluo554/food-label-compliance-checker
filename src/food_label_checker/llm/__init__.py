"""LLM 兜底适配器（M4 实现，plan/02 FR-13）。

边界纪律：LLM 只做非结构化抽取兜底、别名归一、复核、报告行文；
数值结论永远来自确定性规则。客户端要求：OpenAI 兼容 REST（httpx）、
enable_thinking=false、候选行压缩、输出"原文编号+逐字摘录"且摘录必须是
原文子串、重试+超时、不可达时降级规则通路。全部测试离线 mock。

M4 落地形态：
- LLMConfig / from_env：FOOD_LABEL_LLM_* 环境变量与 .env 读配置，默认关闭；
- LLMClient：OpenAI 兼容 chat/completions，enable_thinking=false，重试+超时，
  一切失败抛 LLMUnavailable；
- apply_fallback：候选行压缩 → 字段定位 → quote ⊆ 原文逐字校验 → 回填参数卡
  （confidence=0.7、region="LLM 兜底"、llm_assisted=True）；
- 降级：不可达/超时/配置缺失/响应不可解析 → status="degraded"，规则层按
  既有语义处理 unresolved（不吞结论、不造结论）。
"""
from .client import LLMClient, LLMUnavailable
from .config import ENV_PREFIX, LLMConfig, from_env, load_dotenv
from .fallback import FALLBACK_KEYS, apply_fallback, build_messages, candidate_lines

__all__ = [
    "ENV_PREFIX",
    "FALLBACK_KEYS",
    "LLMClient",
    "LLMConfig",
    "LLMUnavailable",
    "apply_fallback",
    "build_messages",
    "candidate_lines",
    "from_env",
    "load_dotenv",
]
