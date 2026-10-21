"""版本号单一来源守门（D12）：`pyproject.toml` 与 `__version__` 必须一致。

改前是两处手写（`pyproject.toml` 的 `version = "0.6.0"` 与
`__init__.py` 的 `__version__ = "0.6.0"`），没有任何一致性守门；`test_version_flag`
只断言输出含 "flcheck"，版本号错了也不会红。抬版本时漏改一处的后果是
`flcheck --version`、wheel 元数据、tag 名三者互相矛盾，而所有测试全绿。

解析方式用 `tomllib`（3.11+；本项目 floor 为 3.12）而不是正则，避免把注释里的
`version = ...` 或 `[tool.*]` 段下的同名键认错。
"""
import sys
from pathlib import Path

import pytest

import food_label_checker

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _pyproject_version():
    if sys.version_info >= (3, 11):
        import tomllib

        with open(PYPROJECT, "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    # 兼容路径：floor 虽为 3.12，但这里留一条不依赖 tomllib 的退路，
    # 免得将来有人在本文件里跑低版本解释器时得到 ImportError 而非清晰断言。
    pytest.importorskip("tomli")  # pragma: no cover
    import tomli  # pragma: no cover

    with open(PYPROJECT, "rb") as fh:  # pragma: no cover
        return tomli.load(fh)["project"]["version"]  # pragma: no cover


def test_version_single_source():
    """pyproject.toml 的 version 与 food_label_checker.__version__ 必须逐字符相同。"""
    declared = _pyproject_version()
    runtime = food_label_checker.__version__
    assert declared == runtime, (
        "版本号有两处手工维护且不一致：\n"
        f"  pyproject.toml  [project].version = {declared!r}\n"
        f"  __init__.py     __version__       = {runtime!r}\n"
        "抬版本时两处必须同步改（D12）"
    )


def test_version_is_pep440_release_tuple():
    """版本号应是 X.Y.Z 形态（tag 名 = v<version>，不能带 .dev / +local 后缀）。"""
    runtime = food_label_checker.__version__
    parts = runtime.split(".")
    assert len(parts) == 3, f"版本号应为 X.Y.Z，实际 {runtime!r}"
    assert all(p.isdigit() for p in parts), f"版本号各段应为数字，实际 {runtime!r}"
