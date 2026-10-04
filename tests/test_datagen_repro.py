"""datagen 守门测试：固定 seed 位级复现 + 冻结 fixtures 对照（HANDOFF-M1 任务 2/5）。

冻结集（data/generated/frozen/seed-2026-n12/）与生成器任一侧变更都会让
test_frozen_fixture_gate 失败——这是"改了就得重生成并升 DATAGEN_VERSION"的强制闸门。
"""
import hashlib
import json
from pathlib import Path

import pytest

from food_label_checker.cli import main
from food_label_checker.datagen import DATAGEN_VERSION, generate_dataset
from food_label_checker.datagen.injectors import V_ORDER

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = REPO_ROOT / "data" / "generated" / "frozen"
FROZEN_MANIFEST_PATH = FROZEN_DIR / "seed-2026-n12" / "manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_map(dataset_dir: Path) -> dict:
    return {p.name: _sha256(p) for p in sorted(dataset_dir.iterdir()) if p.is_file()}


@pytest.fixture
def frozen_manifest():
    assert FROZEN_MANIFEST_PATH.exists(), "冻结 fixtures 缺失，请先按 plan/05 §1.3 生成"
    return json.loads(FROZEN_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_gen_cli_creates_dataset(tmp_path, capsys):
    assert main(["gen", "--seed", "42", "--n", "12", "--out", str(tmp_path)]) == 0
    target = tmp_path / "seed-42-n12"
    files = {p.name for p in target.iterdir()}
    assert "truth.json" in files and "manifest.json" in files
    assert len([f for f in files if f.endswith(".txt")]) == 12

    truth = json.loads((target / "truth.json").read_text(encoding="utf-8"))
    assert truth["seed"] == 42 and truth["n"] == 12
    assert len(truth["samples"]) == 12
    assert "生成完成" in capsys.readouterr().out


def test_seed_bitwise_reproducible(tmp_path):
    assert main(["gen", "--seed", "7", "--n", "12", "--out", str(tmp_path / "a")]) == 0
    assert main(["gen", "--seed", "7", "--n", "12", "--out", str(tmp_path / "b")]) == 0
    assert _hash_map(tmp_path / "a" / "seed-7-n12") == _hash_map(tmp_path / "b" / "seed-7-n12")


def test_different_seed_different_output(tmp_path):
    assert main(["gen", "--seed", "7", "--n", "12", "--out", str(tmp_path)]) == 0
    assert main(["gen", "--seed", "8", "--n", "12", "--out", str(tmp_path)]) == 0
    hashes = (_hash_map(tmp_path / "seed-7-n12"), _hash_map(tmp_path / "seed-8-n12"))
    assert hashes[0] != hashes[1]
    # 同 n 同品类 → 标签文件数量相同；但 seed 影响模板抽取，文件名集合不要求一致
    labels = lambda m: {k for k in m if k.endswith(".txt")}
    assert len(labels(hashes[0])) == len(labels(hashes[1])) == 12


def test_existing_dir_requires_force(tmp_path, capsys):
    assert main(["gen", "--seed", "42", "--n", "12", "--out", str(tmp_path)]) == 0
    assert main(["gen", "--seed", "42", "--n", "12", "--out", str(tmp_path)]) == 2
    assert "--force" in capsys.readouterr().err
    before = _hash_map(tmp_path / "seed-42-n12")
    assert main(["gen", "--seed", "42", "--n", "12", "--out", str(tmp_path), "--force"]) == 0
    assert _hash_map(tmp_path / "seed-42-n12") == before  # --force 重生成位级一致


def test_unknown_category_exit_2(tmp_path, capsys):
    assert main(["gen", "--seed", "42", "--categories", "日化", "--out", str(tmp_path)]) == 2
    assert "未知品类" in capsys.readouterr().err


def test_bad_n_exit_2(tmp_path, capsys):
    assert main(["gen", "--seed", "42", "--n", "0", "--out", str(tmp_path)]) == 2
    assert "--n" in capsys.readouterr().err


def test_truth_schema(tmp_path):
    assert main(["gen", "--seed", "2026", "--n", "12", "--out", str(tmp_path)]) == 0
    truth = json.loads((tmp_path / "seed-2026-n12" / "truth.json").read_text(encoding="utf-8"))
    for s in truth["samples"]:
        for key in ("sample_id", "file", "seed", "rng_key", "generator_version",
                    "category", "template", "clean_baseline", "injections"):
            assert key in s, f"真值样本缺字段 {key}: {s['sample_id']}"
        assert s["generator_version"] == DATAGEN_VERSION
        assert s["rng_key"] == f"{s['seed']}:" + s["rng_key"].split(":", 1)[1]  # 派生可审计
        if s["clean_baseline"]:
            assert s["injections"] == [], f"干净版不得有注入：{s['sample_id']}"
        for inj in s["injections"]:
            assert inj["type"] in V_ORDER
            assert inj["main_expect"]["level"] == "不合规"
            assert inj["main_expect"]["rule_id"]
            for extra in inj["also_expect"]:
                assert ("rule_id" in extra) or ("kind" in extra and extra["kind"] == "info")


def test_frozen_covers_all_categories_and_v_types(frozen_manifest):
    truth = json.loads(
        (FROZEN_DIR / "seed-2026-n12" / "truth.json").read_text(encoding="utf-8")
    )
    assert truth["generator_version"] == frozen_manifest["generator_version"]
    cats = {s["category"] for s in truth["samples"] if s["clean_baseline"]}
    assert cats == set(frozen_manifest["categories"]), "每品类至少 1 个干净版"
    injected_types = {i["type"] for s in truth["samples"] for i in s["injections"]}
    assert injected_types == set(V_ORDER), "冻结集必须覆盖 V1–V8 全部注入类型"


def test_frozen_fixture_gate(tmp_path, frozen_manifest):
    """核心闸门：按冻结集参数重生成，所有文件 sha256 必须与入仓冻结集一致。"""
    seed, n = frozen_manifest["seed"], frozen_manifest["n"]
    cats = ",".join(frozen_manifest["categories"])
    assert main(["gen", "--seed", str(seed), "--n", str(n), "--categories", cats,
                 "--out", str(tmp_path)]) == 0
    regen = tmp_path / f"seed-{seed}-n{n}"
    # manifest.json 自身不在 files 映射里（自引用不可能），单独字节比对在下方
    assert {p.name for p in regen.iterdir()} - {"manifest.json"} == set(frozen_manifest["files"])
    for name, expected_hash in frozen_manifest["files"].items():
        assert _sha256(regen / name) == expected_hash, f"位级漂移：{name}"
    assert (regen / "manifest.json").read_bytes() == FROZEN_MANIFEST_PATH.read_bytes()


def test_dataset_pure_function_matches_written_files(tmp_path):
    """generate_dataset 纯函数输出与 CLI 落盘文件一致（间接守卫渲染/写入路径）。"""
    truth, texts = generate_dataset(2026, 12)
    frozen = FROZEN_DIR / "seed-2026-n12"
    for name, text in texts.items():
        assert (frozen / name).read_text(encoding="utf-8") == text
    assert json.loads((frozen / "truth.json").read_text(encoding="utf-8")) == truth
