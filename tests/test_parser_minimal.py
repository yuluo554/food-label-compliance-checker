"""文本解析器最小回归测试。

关键性质：证据 quote 必须是输入文本的逐字子串（防幻觉硬校验）。
全字段值回归与 F1 自测见 test_parser_frozen.py；字段级变体见 test_parser_fields.py。
"""
from food_label_checker.parser import parse_label

MINI_LABEL = "食品名称：牧云 发酵乳\n净含量：250 mL\n生产日期：2026年09月20日\n配料：生牛乳、白砂糖\n保质期：21天\n"


def test_parse_mini_label_fields():
    card = parse_label(MINI_LABEL)
    assert card.get("food_name").value == "牧云 发酵乳"
    net = card.get("net_content")
    assert net.value == {"amount": 250.0, "unit": "mL"}
    # M2 契约：日期字段 value=ISO，原样标示文本在 evidence.quote（见 plan/06 D19）
    prod = card.get("production_date")
    assert prod.value == "2026-09-20"
    assert prod.evidence.quote == "2026年09月20日"


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


def test_former_hint_lines_now_parsed(sample_text):
    """M0 骨架期这些行只进 unresolved 提示，M2 起全字段解析到位。"""
    card = parse_label(sample_text)
    assert card.has("ingredients")
    assert card.has("shelf_life")
    assert card.has("storage_conditions")
    assert card.has("sc_license")
    assert card.has("producer_name")
    assert card.has("product_standard")
    assert not any("待 M2 解析" in item for item in card.unresolved)
