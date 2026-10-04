"""最小文本解析器回归测试。

关键性质：证据 quote 必须是输入文本的逐字子串（防幻觉硬校验）。
"""
from food_label_checker.parser import parse_label

MINI_LABEL = "食品名称：牧云 发酵乳\n净含量：250 mL\n生产日期：2026年09月20日\n配料：生牛乳、白砂糖\n保质期：21天\n"


def test_parse_mini_label_fields():
    card = parse_label(MINI_LABEL)
    assert card.get("food_name").value == "牧云 发酵乳"
    net = card.get("net_content")
    assert net.value == {"amount": 250.0, "unit": "mL"}
    assert card.get("production_date").value == "2026年09月20日"


def test_evidence_quote_is_literal_substring():
    card = parse_label(MINI_LABEL)
    for field in card.fields.values():
        assert field.evidence is not None
        assert field.evidence.quote in MINI_LABEL
        assert field.evidence.region


def test_missing_mandatory_lines_go_unresolved(sample_text):
    card = parse_label(sample_text)
    # 样例标签故意不含净含量：必须显式进 unresolved，而不是静默缺失
    assert any("净含量" in item for item in card.unresolved)
    assert not card.has("net_content")
    assert card.has("food_name")
    assert card.has("production_date")


def test_unparsed_hint_lines_collected(sample_text):
    card = parse_label(sample_text)
    joined = "\n".join(card.unresolved)
    for hint in ("配料", "保质期", "贮存", "许可证"):
        assert hint in joined
