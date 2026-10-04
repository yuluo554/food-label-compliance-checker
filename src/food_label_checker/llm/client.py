"""OpenAI 兼容 REST 客户端（httpx 可选依赖，[llm] extra）。

边界纪律（plan/02 FR-13）：LLM 只做非结构化抽取兜底/别名归一/复核/报告行文，
数值结论永远来自确定性规则。请求体固定 enable_thinking=false（关闭思维链，
保证延迟与输出形态稳定）；传输错误/超时/HTTP 错误/响应异常统一抛
LLMUnavailable，由调用方降级到规则通路（plan/04 §5）。全部测试使用
httpx.MockTransport 或 stub，零真实 API 调用。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class LLMUnavailable(Exception):
    """LLM 不可用：httpx 未安装 / 配置缺失 / 网络不可达 / 超时 / HTTP 错误 / 响应异常。"""


class LLMClient:
    """OpenAI 兼容 chat/completions 客户端（最小面：只用到 chat 一个操作）。"""

    def __init__(self, config, transport=None):
        self.config = config
        self._transport = transport  # 测试注入 httpx.MockTransport

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """发送对话补全请求，返回首条回复文本；任何失败抛 LLMUnavailable。"""
        problems = self.config.missing_required()
        if problems:
            raise LLMUnavailable("LLM 配置缺失：" + "、".join(problems))
        try:
            import httpx
        except ImportError as exc:
            raise LLMUnavailable(
                "httpx 未安装：pip install 'food-label-compliance-checker[llm]'"
            ) from exc

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "enable_thinking": False,  # 关闭思维链（OpenAI 兼容扩展参数）
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        attempts = max(1, int(self.config.max_retries) + 1)

        last_reason = "未知错误"
        with httpx.Client(timeout=self.config.timeout_seconds, transport=self._transport) as client:
            for attempt in range(attempts):
                try:
                    resp = client.post(url, json=payload, headers=headers)
                except httpx.TransportError as exc:  # 含超时/连接失败
                    last_reason = f"网络错误：{type(exc).__name__}: {exc}"
                    resp = None
                if resp is not None:
                    if resp.status_code < 400:
                        return self._extract_content(resp)
                    last_reason = f"HTTP {resp.status_code}：{resp.text[:200]}"
                    if resp.status_code < 500:
                        break  # 4xx 客户端错误重试无意义
                if attempt < attempts - 1:
                    time.sleep(min(0.5 * (2 ** attempt), 2.0))
        raise LLMUnavailable(f"LLM 不可用（已重试 {attempts} 次）：{last_reason}")

    @staticmethod
    def _extract_content(resp) -> str:
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:  # JSON/结构异常统一视为不可用
            raise LLMUnavailable(f"LLM 响应解析失败：{type(exc).__name__}: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailable("LLM 响应 content 为空")
        return content
