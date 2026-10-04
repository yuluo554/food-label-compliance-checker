"""M5 pipeline 状态机：节点 trace 结构、load_input 读取、输入类失败、规则类降级。"""
import pytest

import food_label_checker.pipeline as pl
from food_label_checker.pipeline import (
    NODE_DEGRADED,
    NODE_OK,
    NODE_SKIPPED,
    check_text,
    run_pipeline,
)

EXPECTED_NODES = [
    "load_input",
    "parse",
    "llm_fallback",
    "run_ruleset:gb7718-2011",
    "run_ruleset:gb7718-2025",
    "merge_diff",
    "emit",
]


def test_node_trace_structure_and_contract_keys(sample_text):
    """节点顺序/状态合法/耗时非负；M4 结果键契约不破坏。"""
    out = check_text(sample_text, ["gb7718-2011", "gb7718-2025"])
    nodes = out["pipeline"]["nodes"]
    assert [n["node"] for n in nodes] == EXPECTED_NODES
    for n in nodes:
        assert n["status"] in (NODE_OK, NODE_SKIPPED, NODE_DEGRADED)
        assert n["elapsed_ms"] >= 0
        assert isinstance(n["detail"], str) and n["detail"]
    by_name = {n["node"]: n for n in nodes}
    assert by_name["load_input"]["status"] == NODE_SKIPPED
    assert by_name["parse"]["status"] == NODE_OK
    assert by_name["llm_fallback"]["status"] == NODE_SKIPPED  # 默认关闭
    for key in ("engine_version", "ruleset_ids", "card", "fallback", "results",
                "pipeline", "warnings", "dual_diff"):
        assert key in out
    assert out["warnings"] == []


def test_load_input_node_reads_file(sample_text, tmp_path):
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    out = run_pipeline(input_path=target, ruleset_ids=["gb7718-2011"])
    node = out["pipeline"]["nodes"][0]
    assert node["node"] == "load_input" and node["status"] == NODE_OK
    assert "label.txt" in node["detail"] and str(len(sample_text)) in node["detail"]
    assert set(out["results"]) == {"gb7718-2011"}


def test_input_class_failure_raises(tmp_path):
    """输入类失败明确报错退出（CLI 映射退出码 2），不做降级。"""
    with pytest.raises(FileNotFoundError):
        run_pipeline(input_path=tmp_path / "nope.txt", ruleset_ids=["gb7718-2011"])
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\x00\x01not-utf8")
    with pytest.raises(ValueError):
        run_pipeline(input_path=bad, ruleset_ids=["gb7718-2011"])


def test_ruleset_failure_degrades_not_swallowed(sample_text, monkeypatch):
    """规则类失败：该 ruleset 结果缺失 + 降级节点 + 警告；异常详情不被吞掉。"""
    real_run = pl.run_ruleset

    def flaky(card, ruleset):
        if ruleset["ruleset_id"] == "gb7718-2011":
            raise RuntimeError("规则集 2011 炸了")
        return real_run(card, ruleset)

    monkeypatch.setattr(pl, "run_ruleset", flaky)
    out = check_text(sample_text, ["gb7718-2011", "gb7718-2025"])
    node = next(n for n in out["pipeline"]["nodes"]
                if n["node"] == "run_ruleset:gb7718-2011")
    assert node["status"] == NODE_DEGRADED
    assert "RuntimeError" in node["detail"] and "规则集 2011 炸了" in node["detail"]
    assert "gb7718-2011" not in out["results"]
    assert "gb7718-2025" in out["results"]
    assert out["warnings"] and "run_ruleset:gb7718-2011" in out["warnings"][0]
    merge = next(n for n in out["pipeline"]["nodes"] if n["node"] == "merge_diff")
    assert merge["status"] == NODE_DEGRADED
    assert "dual_diff" not in out  # 一侧结果缺失 → 对照跳过
    healthy = next(n for n in out["pipeline"]["nodes"]
                   if n["node"] == "run_ruleset:gb7718-2025")
    assert healthy["status"] == NODE_OK


def test_llm_degraded_node_trace(sample_text, monkeypatch):
    """LLM 兜底不可达：llm_fallback 节点降级 + 原因入 trace，审查照常完成。"""
    from food_label_checker.llm.client import LLMUnavailable
    from food_label_checker.llm.config import LLMConfig

    class StubClient:
        def __init__(self, cfg):
            pass

        def chat(self, messages):
            raise LLMUnavailable("连接超时")

    monkeypatch.setattr("food_label_checker.llm.client.LLMClient", StubClient)
    cfg = LLMConfig(enabled=True, base_url="https://x/v1", api_key="k", model="m")
    out = check_text(sample_text, ["gb7718-2011"], llm_config=cfg)
    node = next(n for n in out["pipeline"]["nodes"] if n["node"] == "llm_fallback")
    assert node["status"] == NODE_DEGRADED and "连接超时" in node["detail"]
    assert out["fallback"]["status"] == "degraded"
    assert out["results"]  # 规则通路结论保留
