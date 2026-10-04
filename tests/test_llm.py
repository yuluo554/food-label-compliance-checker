"""LLM 兜底适配器测试（M4）——全部离线 mock，零真实 API 调用。

覆盖：配置（默认关闭/环境变量/.env/优先级）、客户端（enable_thinking=false、
重试、超时、HTTP 错误、响应异常、httpx 缺失）、兜底（quote ⊆ 原文逐字校验、
值从 quote 派生、防幻觉拒绝、降级）、pipeline/CLI 集成与降级语义。
"""
import json
import sys

import pytest

from food_label_checker.llm import LLMClient, LLMConfig, LLMUnavailable
from food_label_checker.llm.config import from_env
from food_label_checker.llm.fallback import (
    FALLBACK_KEYS,
    apply_fallback,
    build_messages,
    candidate_lines,
)
from food_label_checker.models import LEVEL_MANUAL
from food_label_checker.parser import parse_label
from food_label_checker.pipeline import check_text
from food_label_checker.rules.engine import load_ruleset, run_ruleset


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def test_config_default_disabled():
    cfg = from_env(env={})
    assert cfg.enabled is False
    assert cfg.timeout_seconds == 30.0 and cfg.max_retries == 2
    assert set(cfg.missing_required()) == {
        "FOOD_LABEL_LLM_BASE_URL", "FOOD_LABEL_LLM_MODEL", "FOOD_LABEL_LLM_API_KEY",
    }


def test_config_from_env_and_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# 注释\n"
        "FOOD_LABEL_LLM_BASE_URL=https://dotenv.example/v1\n"
        "FOOD_LABEL_LLM_MODEL=d dotenv-model\n"
        "FOOD_LABEL_LLM_API_KEY='quoted-key'\n"
        "FOOD_LABEL_LLM_ENABLED=1\n",
        encoding="utf-8",
    )
    cfg = from_env(env={}, dotenv_path=dotenv)
    assert cfg.enabled is True
    assert cfg.base_url == "https://dotenv.example/v1"
    assert cfg.api_key == "quoted-key"  # 引号剥离

    # 真实环境变量优先于 .env
    cfg2 = from_env(
        env={"FOOD_LABEL_LLM_BASE_URL": "https://env.example/v1"}, dotenv_path=dotenv
    )
    assert cfg2.base_url == "https://env.example/v1"
    assert cfg2.model == "d dotenv-model"


def test_config_bad_numerics_fall_back_to_defaults():
    cfg = from_env(env={
        "FOOD_LABEL_LLM_TIMEOUT_SECONDS": "abc",
        "FOOD_LABEL_LLM_MAX_RETRIES": "x",
    })
    assert cfg.timeout_seconds == 30.0 and cfg.max_retries == 2


# ---------------------------------------------------------------------------
# 客户端（httpx.MockTransport，零网络）
# ---------------------------------------------------------------------------

httpx = pytest.importorskip("httpx")


def _client(cfg, handler):
    return LLMClient(cfg, transport=httpx.MockTransport(handler))


def _cfg(**kw):
    return LLMConfig(
        base_url="https://api.example/v1", api_key="sk-test", model="test-model",
        timeout_seconds=5, max_retries=kw.pop("max_retries", 0), enabled=True, **kw
    )


def test_client_success_and_payload_contract():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": " hi "}}]})

    out = _client(_cfg(), handler).chat([{"role": "user", "content": "x"}])
    assert out == " hi "
    assert seen["url"] == "https://api.example/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["payload"]["model"] == "test-model"
    assert seen["payload"]["enable_thinking"] is False  # 思维链关闭（契约）
    assert seen["payload"]["stream"] is False


def test_client_4xx_no_retry():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(LLMUnavailable, match="HTTP 401"):
        _client(_cfg(), handler).chat([{"role": "user", "content": "x"}])
    assert len(calls) == 1  # 客户端错误不重试


def test_client_5xx_retries_then_unavailable():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, text="overloaded")

    with pytest.raises(LLMUnavailable, match="已重试 3 次"):
        _client(_cfg(max_retries=2), handler).chat([{"role": "user", "content": "x"}])
    assert len(calls) == 3


def test_client_transport_error_retries_then_unavailable():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMUnavailable, match="网络错误"):
        _client(_cfg(max_retries=1), handler).chat([{"role": "user", "content": "x"}])
    assert len(calls) == 2


def test_client_missing_content_unavailable():
    def handler(request):
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(LLMUnavailable, match="解析失败|content"):
        _client(_cfg(), handler).chat([{"role": "user", "content": "x"}])


def test_client_config_missing_unavailable_no_http():
    cfg = LLMConfig(enabled=True)  # 缺全部必填
    with pytest.raises(LLMUnavailable, match="配置缺失"):
        LLMClient(cfg).chat([{"role": "user", "content": "x"}])


def test_client_httpx_missing_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "httpx", None)
    with pytest.raises(LLMUnavailable, match="httpx 未安装"):
        LLMClient(_cfg()).chat([{"role": "user", "content": "x"}])


# ---------------------------------------------------------------------------
# 兜底（stub 客户端）
# ---------------------------------------------------------------------------

class StubClient:
    def __init__(self, content=None, exc=None):
        self.content = content
        self.exc = exc
        self.calls = []

    def chat(self, messages, temperature=0.0):
        self.calls.append(messages)
        if self.exc is not None:
            raise self.exc
        return self.content


def _card(text):
    return parse_label(text)


def test_candidate_lines_compression():
    text = "\n".join(["行%d" % i for i in range(200)])
    out = candidate_lines(text, max_lines=10)
    assert len(out.splitlines()) == 11  # 10 行 + 截断提示
    assert "共 200 行" in out
    long_text = "x" * 9999
    assert len(candidate_lines(long_text, max_chars=100)) <= 130


def test_build_messages_covers_candidates():
    msgs = build_messages("候选", ["food_name", "net_content"])
    assert msgs[0]["role"] == "system" and "逐字子串" in msgs[0]["content"]
    assert "food_name" in msgs[1]["content"] and "候选" in msgs[1]["content"]


def test_fallback_fills_missing_field_with_quote_derived_value():
    text = "食品名称：测试乳\n生产日期 2026年09月12日喷码\n"
    card = _card(text)
    assert card.get("production_date") is None  # 无冒号 → 解析层未捕获

    stub = StubClient(content=json.dumps(
        [{"key": "production_date", "found": True,
          "quote": "生产日期 2026年09月12日喷码", "value": "随便写的值"}],
        ensure_ascii=False))
    report = apply_fallback(card, text, stub)
    assert report["status"] == "applied" and report["filled_keys"] == ["production_date"]
    assert card.llm_assisted is True
    fld = card.get("production_date")
    # 值从校验通过的 quote 重新解析（2026-09-12），不信任 LLM 的 value 字段
    assert fld.value == "2026-09-12"
    assert fld.evidence.region == "LLM 兜底" and fld.confidence < 1.0
    assert text[fld.evidence.span[0]:fld.evidence.span[1]] == fld.evidence.quote
    assert "production_date" not in card.unresolved_detail


def test_fallback_rejects_non_substring_quote():
    text = "食品名称：测试乳\n"
    card = _card(text)
    stub = StubClient(content=json.dumps(
        [{"key": "net_content", "found": True, "quote": "净含量：250 mL", "value": ""}],
        ensure_ascii=False))
    report = apply_fallback(card, text, stub)
    assert report["filled_keys"] == []
    assert report["rejected"][0]["reason"].startswith("quote 非原文逐字子串")
    assert card.llm_assisted is False
    assert card.get("net_content") is None


def test_fallback_not_found_and_fenced_json():
    text = "食品名称缺失的标签\n配料：水\n"
    stub = StubClient(content="```json\n"
                      "[{\"key\": \"food_name\", \"found\": true, "
                      "\"quote\": \"食品名称缺失的标签\", \"value\": \"标签\"}, "
                      "{\"key\": \"net_content\", \"found\": false, \"quote\": \"\", \"value\": \"\"}]"
                      "\n```")
    card = _card(text)
    report = apply_fallback(card, text, stub)
    assert report["status"] == "applied"
    assert report["filled_keys"] == ["food_name"]  # found=false 的键跳过
    assert card.get("food_name").value == "标签"


def test_fallback_degraded_on_unavailable():
    text = "食品名称：测试乳\n净含量：计量称重\n"
    card = _card(text)
    stub = StubClient(exc=LLMUnavailable("网络错误：ConnectError"))
    report = apply_fallback(card, text, stub)
    assert report["status"] == "degraded" and "ConnectError" in report["reason"]
    assert card.llm_assisted is False
    assert card.get("net_content") is None
    assert card.unresolved_detail["net_content"] == "present_unparsed"


def test_fallback_degraded_on_bad_json():
    stub = StubClient(content="这不是 JSON")
    text = "食品名称：测试乳\n"
    report = apply_fallback(_card(text), text, stub)
    assert report["status"] == "degraded"
    assert "JSON" in report["reason"]


def test_fallback_not_needed_when_complete():
    text = (
        "食品名称：测试乳\n配料：水\n净含量：1g\n生产日期：2026年09月12日\n"
        "保质期：6个月\n保质期到期日：2027年03月12日\n贮存条件：常温\n"
        "生产商：某厂\n地址：某地\n联系方式：400-000-0000\n"
        "食品生产许可证编号：SC12345678901234\n产品标准代号：GB 1234\n"
    )
    report = apply_fallback(_card(text), text, StubClient(content="[]"))
    assert report["status"] == "not_needed"


def test_fallback_degraded_then_rule_manual_semantics():
    """降级语义端到端：LLM 不可达时，行在值不可析 → 待人工确认（不吞结论）。"""
    text = "食品名称：测试乳\n净含量：计量称重\n"
    card = _card(text)
    report = apply_fallback(card, text, StubClient(exc=LLMUnavailable("超时")))
    assert report["status"] == "degraded"
    result = run_ruleset(card, load_ruleset("gb7718-2011"))
    net = next(f for f in result.findings if f.rule_id == "MAND-NET-01")
    assert net.level == LEVEL_MANUAL


# ---------------------------------------------------------------------------
# pipeline / CLI 集成
# ---------------------------------------------------------------------------

def test_pipeline_llm_off_by_default(sample_text):
    out = check_text(sample_text, ["gb7718-2011"])
    assert out["fallback"]["status"] == "off" and out["fallback"]["enabled"] is False


def test_pipeline_llm_applied_with_stub(monkeypatch, sample_text):
    stub = StubClient(content="[]")  # 响应合法但无可回填项

    monkeypatch.setattr("food_label_checker.llm.client.LLMClient",
                        lambda cfg: stub)
    cfg = LLMConfig(enabled=True, base_url="https://x/v1", api_key="k", model="m")
    out = check_text(sample_text, ["gb7718-2011"], llm_config=cfg)
    assert out["fallback"]["status"] == "applied"
    assert out["fallback"]["enabled"] is True
    assert stub.calls, "pipeline 应调用 LLM 兜底"


def test_pipeline_llm_disabled_config_not_used(sample_text, monkeypatch):
    def _boom(cfg):
        raise AssertionError("enabled=False 时不得构造/调用客户端")

    monkeypatch.setattr("food_label_checker.llm.client.LLMClient", _boom)
    cfg = LLMConfig(enabled=False)
    out = check_text(sample_text, ["gb7718-2011"], llm_config=cfg)
    assert out["fallback"]["status"] == "off"


def test_cli_check_llm_flag_degrades_without_config(sample_text, tmp_path, capsys, monkeypatch):
    """--llm 开启但未配置 → 兜底降级（报告原因），审查照常完成（退出码 0）。"""
    from food_label_checker.cli import main

    for var in ("FOOD_LABEL_LLM_ENABLED", "FOOD_LABEL_LLM_BASE_URL",
                "FOOD_LABEL_LLM_API_KEY", "FOOD_LABEL_LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # 无 .env
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["check", str(target), "--ruleset", "2011", "--llm"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fallback"]["status"] == "degraded"
    assert "配置缺失" in payload["fallback"]["reason"]
    assert payload["results"]["gb7718-2011"]["stats"]["fail"] >= 1  # 规则通路照常


def test_cli_check_default_off(sample_text, tmp_path, capsys):
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    from food_label_checker.cli import main

    assert main(["check", str(target)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fallback"]["status"] == "off"


def test_fallback_keys_contract():
    """兜底候选键必须是 P0 行字段（营养表/声称有专用通路，不得混入）。"""
    keys = [k for k, _ in FALLBACK_KEYS]
    assert "nutrition_table" not in keys and "claims" not in keys
    assert "allergen_notice" not in keys and "salt_oil_sugar_notice" not in keys
    assert "net_content" in keys and "sc_license" in keys
