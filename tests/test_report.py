"""M5 docx 审查报告：结构、0 外链（rels 无 External）、LLM 标注、待人工独立成节。"""
import zipfile

import pytest

from food_label_checker.pipeline import check_text

docx = pytest.importorskip("docx")

from food_label_checker.report.docx_report import generate_report  # noqa: E402


def _document_xml(path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_report_structure_with_fails(sample_text, tmp_path):
    """示例标签含不合规项：七节结构齐全，问题清单非空。"""
    result = check_text(sample_text, ["gb7718-2011", "gb7718-2025"])
    out = tmp_path / "r.docx"
    assert generate_report(result, out) == out
    doc = _document_xml(out)
    for marker in (
        "预包装食品标签合规审查报告",
        "一、结论摘要",
        "二、问题清单（不合规）",
        "三、待人工确认",
        "四、证据表",
        "五、整改建议",
        "六、审查员签署栏",
        "七、免责声明",
    ):
        assert marker in doc, f"缺少章节：{marker}"
    assert "未发现不合规项" not in doc  # 示例标签 2011/2025 均有不合规项
    assert "MAND-" in doc  # 问题清单含规则 ID
    # 元信息：引擎版本与规则集
    assert result["engine_version"] in doc
    assert "gb7718-2011" in doc and "gb7718-2025" in doc


def test_report_manual_section_independent(tmp_path):
    """行在值不可析 → 待人工确认独立成节（不与不合规混列）。"""
    text = "食品名称：测试乳\n净含量：计量称重\n"
    result = check_text(text, ["gb7718-2011"])
    out = tmp_path / "m.docx"
    generate_report(result, out)
    doc = _document_xml(out)
    assert "三、待人工确认" in doc
    assert "MAND-NET-01" in doc  # 净含量 present_unparsed → 待人工
    assert "未经复核不得作为最终结论" in doc


def test_report_rels_no_external(sample_text, tmp_path):
    """0 外链纪律：docx 全部 rels 包件不得出现 TargetMode="External"。"""
    result = check_text(sample_text, ["gb7718-2011", "gb7718-2025"])
    out = tmp_path / "r.docx"
    generate_report(result, out)
    with zipfile.ZipFile(out) as z:
        rels = [n for n in z.namelist() if n.endswith(".rels")]
        assert rels, "docx 应包含 rels 包件"
        for name in rels:
            content = z.read(name).decode("utf-8")
            assert 'TargetMode="External"' not in content, f"{name} 含外部链接"


def test_report_llm_assisted_annotation(tmp_path, sample_text):
    """card.llm_assisted=True → 报告元信息与免责声明标注 LLM 参与。"""
    result = check_text(sample_text, ["gb7718-2011"])
    result["card"]["llm_assisted"] = True
    out = tmp_path / "llm.docx"
    generate_report(result, out)
    doc = _document_xml(out)
    assert "LLM 兜底参与：是" in doc
    assert "数值结论均来自确定性规则" in doc


def test_report_llm_off_default(tmp_path, sample_text):
    result = check_text(sample_text, ["gb7718-2011"])
    out = tmp_path / "off.docx"
    generate_report(result, out)
    doc = _document_xml(out)
    assert "LLM 兜底参与：否" in doc


def test_report_parent_dir_created(tmp_path, sample_text):
    result = check_text(sample_text, ["gb7718-2011"])
    out = tmp_path / "sub" / "dir" / "r.docx"
    generate_report(result, out)
    assert out.exists()
