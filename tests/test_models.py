"""参数卡数据模型基本行为。"""
import json

from food_label_checker.models import Evidence, LabelCard, LabelField


def test_card_has_get_roundtrip():
    card = LabelCard()
    card.fields["food_name"] = LabelField(
        key="food_name", value="测试乳", evidence=Evidence(region="名称栏", quote="食品名称：测试乳")
    )
    assert card.has("food_name")
    assert card.get("food_name").value == "测试乳"
    assert not card.has("net_content")
    assert card.get("net_content") is None


def test_card_to_dict_json_serializable():
    card = LabelCard()
    card.fields["net_content"] = LabelField(
        key="net_content",
        value={"amount": 250.0, "unit": "mL"},
        unit="mL",
        evidence=Evidence(region="净含量行", quote="净含量：250 mL", span=(0, 12)),
    )
    card.unresolved.append("待 M2 解析：配料：生牛乳")
    data = card.to_dict()
    # 可直接 JSON 序列化（CLI 输出通路）
    restored = json.loads(json.dumps(data, ensure_ascii=False))
    assert restored["fields"]["net_content"]["value"]["amount"] == 250.0
    assert restored["unresolved"] == ["待 M2 解析：配料：生牛乳"]
