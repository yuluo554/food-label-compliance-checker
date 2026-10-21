"""bench 评测器与 CLI 守门（M4，plan/04 §6 / plan/05 M4 DoD）。

门槛（HANDOFF-M4 既定口径）：解析 F1 ≥ 0.95；e2e 误报 0、检出率 1.0、
dual_diff 零违例（M3 在冻结集固化的合格线，D21）。评测输入读冻结 fixtures
（只读，D18），期望值由生成器内存重建，禁止语料反提。
"""
import json
from pathlib import Path

import pytest

from food_label_checker.bench.e2e_eval import evaluate_e2e
from food_label_checker.bench.parse_eval import (
    PARSE_F1_GATE,
    evaluate_frozen,
    resolve_bench_data,
)
from food_label_checker.cli import main
from food_label_checker.datagen import generate_dataset, write_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "data" / "generated" / "frozen" / "seed-2026-n12"

# 跨 seed 守门用的种子表（D5）：冻结集只钉住 seed=2026，单点达标不代表任意
# seed 达标。DEC-1=A 之前，15 个种子里有 11 个检出率掉到 0.875~0.9。
CROSS_SEEDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 42, 99, 2026)


def test_bench_parse_gate_on_frozen():
    """M4 DoD：全量冻结集解析 F1 ≥ 0.95（实测应为 1.0）。"""
    metrics, issues = evaluate_frozen(data_dir=FROZEN_DIR)
    assert not issues, issues[:5]
    assert metrics["f1"] >= PARSE_F1_GATE
    assert metrics["precision"] >= PARSE_F1_GATE
    assert metrics["recall"] >= PARSE_F1_GATE


def test_bench_e2e_gate_on_frozen():
    """M4 DoD：误报 0、检出率 1.0、dual_diff 零违例、待人工不参与对账。"""
    metrics, issues = evaluate_e2e(data_dir=FROZEN_DIR)
    assert not issues, issues[:5]
    assert metrics["false_positives"] == 0
    assert metrics["detection_rate"] == 1.0
    assert metrics["clean_baseline_violations"] == []
    assert metrics["absent_in_violations"] == []
    assert metrics["dual_diff_violations"] == []
    assert metrics["manual_findings_info_only"] == 0
    assert metrics["covered_instances"] == metrics["fail_instances"]
    assert metrics["main_expect_total"] > 0


def test_bench_e2e_gate_across_seeds(tmp_path):
    """D5 回归：任意 seed 生成的数据集都必须满足 e2e 门槛，不只是冻结集那个 seed。

    冻结集只覆盖 seed=2026。DEC-1=A 之前 beverage-tea 模板声明支持 V6，而规则
    ING-ORDER-01 的 only_if 不覆盖茶饮料品名 → 门控 skipped → 注入真值检不出，
    15 个种子里 11 个掉到 0.875~0.9。本测试把「任意 seed 达标」变成可机判事实。
    """
    failures = []
    for seed in CROSS_SEEDS:
        truth, texts = generate_dataset(seed, 12)
        data_dir = write_dataset(truth, texts, tmp_path)
        metrics, issues = evaluate_e2e(data_dir=data_dir)
        if issues or metrics["detection_rate"] != 1.0 or metrics["false_positives"] != 0:
            failures.append(
                f"seed={seed} detection_rate={metrics['detection_rate']} "
                f"false_positives={metrics['false_positives']} issues={issues[:3]}"
            )
    assert not failures, "\n".join(failures)


def test_bench_missing_data_exit_2(capsys):
    with pytest.raises(FileNotFoundError):
        resolve_bench_data("data/generated/nowhere")
    assert main(["bench", "parse", "--data", "data/generated/nowhere"]) == 2
    assert "基准数据集不存在" in capsys.readouterr().err


def test_bench_parse_cli_pass_and_gate_fail_exit_1(capsys):
    assert main(["bench", "parse"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["bench"] == "parse" and payload["gate"]["passed"] is True

    # 门槛不可达时退出码 1（门槛本身可由 --min-f1 调高验证退出路径）
    assert main(["bench", "parse", "--min-f1", "1.01"]) == 1
    gate = json.loads(capsys.readouterr().out)["gate"]
    assert gate["passed"] is False


def test_bench_e2e_cli_pass(capsys):
    assert main(["bench", "e2e"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["bench"] == "e2e" and payload["gate"]["passed"] is True
    assert payload["metrics"]["false_positives"] == 0


def test_bench_bare_command_exit_2(capsys):
    assert main(["bench"]) == 2
    assert "需要子命令" in capsys.readouterr().err
