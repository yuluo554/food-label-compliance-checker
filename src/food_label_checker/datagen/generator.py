"""datagen 数据集组装：样本排程 → 注入 → 渲染 → truth.json + manifest.json。

排程（确定性）：
1. 每个品类 1 个干净版（clean_baseline=true，注入清单为空）；
2. V1–V8 覆盖轮转：V_i 挂到 cats[(i-1) % len(cats)]，模板从支持该注入的小类中 rng 选；
3. n 超过基础数后补"追加样本"：每第 3 个干净，其余随机组合 1–3 类注入。
真值与落盘 schema 见 datagen/__init__.py 模块注释（真值语义定稿）。
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import injectors
from .templates import (
    CATEGORY_TEMPLATES,
    GENERATION_YEAR,
    LabelState,
    Template,
    initial_state,
    render_label,
)

DATAGEN_VERSION = "2"  # v2（M4）：模板补糖行（灭菌乳/食醋 0g）+ 全模板致敏物质提示行；详见 datagen/__init__.py §6
TRUTH_SEMANTICS_NOTE = "主期望+also_expect 语义与对账口径见 datagen/__init__.py 模块注释（M1 定稿）"


def _shuffle(rng: random.Random, seq) -> List[Any]:
    out = list(seq)
    for i in range(len(out) - 1, 0, -1):
        j = rng.randrange(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _plan_samples(n: int, cats: List[str]) -> List[Tuple[str, str, Optional[str]]]:
    """返回 (kind, category, vtype)；vtype=None 的 inject 表示追加样本随机组合。"""
    if n < 1:
        raise ValueError("--n 至少为 1")
    plans: List[Tuple[str, str, Optional[str]]] = []
    for cat in cats:
        plans.append(("clean", cat, None))
    for i in range(1, len(injectors.V_ORDER) + 1):
        plans.append(("inject", cats[(i - 1) % len(cats)], injectors.V_ORDER[i - 1]))
    base = len(plans)
    pos = 0
    while len(plans) < n:
        if pos % 3 == 2:
            plans.append(("clean", cats[pos % len(cats)], None))
        else:
            plans.append(("inject", cats[pos % len(cats)], None))
        pos += 1
    return plans[:n]


def _pick_template(rng: random.Random, cat: str, vtype: Optional[str]) -> Template:
    pool = CATEGORY_TEMPLATES[cat]
    if vtype:
        supporting = [t for t in pool if vtype in t.v_supported]
        if supporting:  # 品类内无支持模板时退化为任意模板（注入将被跳过，防御分支）
            pool = supporting
    return pool[rng.randrange(len(pool))]


def _production_date(rng: random.Random) -> date:
    return date(GENERATION_YEAR, rng.randint(1, 12), rng.randint(1, 28))


def _build_sample(
    rng_key: str, kind: str, cat: str, vtype: Optional[str]
) -> Tuple[Dict[str, Any], str, LabelState]:
    rng = random.Random(rng_key)
    t = _pick_template(rng, cat, vtype)
    state: LabelState = initial_state(t, _production_date(rng))
    entries: List[Dict[str, Any]] = []

    if kind == "inject":
        if vtype:
            if injectors.applicable(state, vtype):
                entries = injectors.apply(state, rng, vtype)
        else:
            chosen = set(_shuffle(rng, [v for v in injectors.V_ORDER if v in t.v_supported])[: rng.randint(1, 3)])
            for v in injectors.V_ORDER:  # 固定 V1→V8 顺序执行，保证确定性
                if v in chosen and injectors.applicable(state, v):
                    entries.extend(injectors.apply(state, rng, v))
        if not entries:
            raise RuntimeError(f"注入样本未产生真值条目（生成器缺陷）：{cat} {vtype}")

    sample = {
        "sample_id": "",  # 由调用方按序号填
        "file": "",
        "seed": None,  # 由调用方填
        "rng_key": rng_key,
        "generator_version": DATAGEN_VERSION,
        "category": t.category,
        "template": t.key,
        "clean_baseline": kind == "clean",
        "injections": entries,
    }
    return sample, render_label(state), state


def generate_dataset_with_states(
    seed: int, n: int, categories: Optional[List[str]] = None
) -> Tuple[Dict[str, Any], Dict[str, str], List[LabelState]]:
    """generate_dataset 超集：额外按样本顺序返回 LabelState。

    M2 起解析层评测（F1）用 State 重建参数卡期望值——期望只能来自生成器的
    构造知识，不能从语料文本反向提取（与被测解析器循环论证）。状态对象不
    消耗随机数，truth/texts 输出与 generate_dataset 位级一致；与冻结 fixtures
    的位级一致性由 tests/test_datagen_repro.py 守门。
    """
    cats = categories if categories else list(CATEGORY_TEMPLATES)
    plans = _plan_samples(n, cats)
    truth: Dict[str, Any] = {
        "generator_version": DATAGEN_VERSION,
        "seed": seed,
        "n": len(plans),
        "categories": list(cats),
        "truth_semantics": TRUTH_SEMANTICS_NOTE,
        "samples": [],
    }
    texts: Dict[str, str] = {}
    states: List[LabelState] = []
    for idx, (kind, cat, vtype) in enumerate(plans):
        sample, text, state = _build_sample(f"{seed}:{idx}", kind, cat, vtype)
        sample["sample_id"] = f"sample-{idx + 1:04d}"
        sample["file"] = f"{sample['sample_id']}-{sample['template']}.txt"
        sample["seed"] = seed
        truth["samples"].append(sample)
        texts[sample["file"]] = text
        states.append(state)
    return truth, texts, states


def generate_dataset(
    seed: int, n: int, categories: Optional[List[str]] = None
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """生成数据集：返回 (truth_dict, {文件名: 标签文本})。纯函数，无副作用。"""
    truth, texts, _ = generate_dataset_with_states(seed, n, categories)
    return truth, texts


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(truth: Dict[str, Any], texts: Dict[str, str]) -> Dict[str, Any]:
    files = {name: _sha256_text(text) for name, text in sorted(texts.items())}
    files["truth.json"] = _sha256_text(dataset_to_json(truth))
    return {
        "generator_version": truth["generator_version"],
        "seed": truth["seed"],
        "n": truth["n"],
        "categories": truth["categories"],
        "files": files,
        "repro": f"flcheck gen --seed {truth['seed']} --n {truth['n']}（--force 覆盖重生成；"
        "位级一致由 tests/test_datagen_repro.py 守门）",
    }


def dataset_to_json(truth: Dict[str, Any]) -> str:
    return json.dumps(truth, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _write_lf(path: Path, text: str) -> None:
    # 3.8 的 Path.write_text 不支持 newline 参数；显式 LF 落盘是 EOL 门的字节一致性前提
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_dataset(
    truth: Dict[str, Any], texts: Dict[str, str], out_root: Path
) -> Path:
    """把数据集写入 <out_root>/seed-<seed>-n<n>/；目标已存在则报错（--force 由 CLI 处理）。"""
    target = out_root / f"seed-{truth['seed']}-n{truth['n']}"
    if target.exists():
        raise FileExistsError(f"目标目录已存在（--force 可覆盖）：{target}")
    target.mkdir(parents=True)
    for name, text in sorted(texts.items()):
        _write_lf(target / name, text)
    _write_lf(target / "truth.json", dataset_to_json(truth))
    manifest = build_manifest(truth, texts)
    _write_lf(
        target / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return target
