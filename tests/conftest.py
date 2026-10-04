"""共享 fixture：示例标签路径与文本。"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_LABEL = REPO_ROOT / "examples" / "sample_label.txt"


@pytest.fixture
def sample_text() -> str:
    return SAMPLE_LABEL.read_text(encoding="utf-8")
