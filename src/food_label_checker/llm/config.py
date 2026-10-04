"""LLM 兜底配置：`FOOD_LABEL_LLM_*` 环境变量 / .env 读取，默认关闭。

字段（前缀 FOOD_LABEL_LLM_）：
- ENABLED          是否启用兜底（1/true/yes/on；CLI --llm 可强制开启）
- BASE_URL         OpenAI 兼容服务根地址（含 /v1，如 https://api.deepseek.com/v1）
- API_KEY          服务密钥（只用于请求头，绝不写入输出/日志）
- MODEL            模型名
- TIMEOUT_SECONDS  请求超时（默认 30）
- MAX_RETRIES      传输失败重试次数（默认 2）

优先级：真实环境变量 > .env（cwd 下）。缺必填项不抛异常——由客户端按
LLMUnavailable 处理，走降级通路（plan/04 §5）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

ENV_PREFIX = "FOOD_LABEL_LLM_"
_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass
class LLMConfig:
    """LLM 兜底运行配置；enabled=False 时 pipeline 完全不感知本模块。"""

    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2
    enabled: bool = False

    def missing_required(self):
        """启用所必需但未配置的项（按检查顺序返回，供降级原因展示）。"""
        problems = []
        if not self.base_url:
            problems.append("FOOD_LABEL_LLM_BASE_URL")
        if not self.model:
            problems.append("FOOD_LABEL_LLM_MODEL")
        if not self.api_key:
            problems.append("FOOD_LABEL_LLM_API_KEY")
        return problems


def load_dotenv(path) -> Dict[str, str]:
    """极简 .env 解析：KEY=VALUE，#注释与空行跳过，值去首尾空白与成对引号。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key.strip():
            out[key.strip()] = value
    return out


def from_env(env: Optional[Mapping[str, str]] = None, dotenv_path=".env") -> LLMConfig:
    """从环境变量与 .env 构建配置（真实环境变量优先）。缺项不报错。"""
    env = os.environ if env is None else env
    file_vars = load_dotenv(dotenv_path)

    def get(name: str, default: str = "") -> str:
        value = env.get(ENV_PREFIX + name, "")
        if value == "":
            value = file_vars.get(ENV_PREFIX + name, default)
        return value

    def get_float(name: str, default: float) -> float:
        try:
            return float(get(name, ""))
        except (TypeError, ValueError):
            return default

    def get_int(name: str, default: int) -> int:
        try:
            return int(float(get(name, "")))
        except (TypeError, ValueError):
            return default

    return LLMConfig(
        base_url=get("BASE_URL").rstrip("/"),
        api_key=get("API_KEY"),
        model=get("MODEL"),
        timeout_seconds=get_float("TIMEOUT_SECONDS", 30.0),
        max_retries=get_int("MAX_RETRIES", 2),
        enabled=get("ENABLED").strip().lower() in _TRUE_VALUES,
    )
