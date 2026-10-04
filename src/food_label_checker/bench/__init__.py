"""内置基准评测（M4，plan/04 §6）：bench parse + bench e2e，零 API 依赖。

- parse_eval：字段级 P/R/F1（门槛 F1≥0.95）。真值参数卡期望值由
  generate_dataset_with_states 内存重建——期望只能来自生成器的构造知识，
  不能从语料文本反向提取（与被测解析器循环论证）；解析输入一律读冻结
  fixtures 文件本身（只读，D18）。
- e2e_eval：双标尺违规检出对账。对账语义（D16 §4，与 tests/test_engine_m3.py
  M3 固化口径等价）：按"全部非 pass（不合规）集合"对账；also_expect 的
  present_in_ruleset/absent_in_ruleset 按字面执行；clean_baseline 样本两把
  标尺零不合规；"待人工确认"不参与对账；dual_diff 仅 V5 产生
  new_fails=[CLAIM-ZEROADD-01]。误报 = 未被真值覆盖的 fail 结论（含
  absent_in 违例与 clean_baseline 误报），目标 0。
"""
from .e2e_eval import DEFAULT_BENCH_DATA, evaluate_e2e, load_bench_dataset
from .parse_eval import evaluate_frozen, resolve_bench_data

__all__ = [
    "DEFAULT_BENCH_DATA",
    "evaluate_e2e",
    "evaluate_frozen",
    "load_bench_dataset",
    "resolve_bench_data",
]
