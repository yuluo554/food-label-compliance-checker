"""M2 字段级解析器单元测试：每个字段解析器的边界行为与别名兼容。

生成器样例回归见 test_parser_frozen.py（冻结集只读）；本文件用构造行覆盖
语料之外的变体（半角冒号、别名、单位归一、V7a 三种非规范日期、缺失提示）。
"""
from food_label_checker.parser import parse_label


def _field(text, key):
    card = parse_label(text)
    return card.get(key)


# --- 行字段：冒号与别名 -------------------------------------------------------

def test_half_width_colon_accepted():
    fld = _field("食品名称: 测试乳\n", "food_name")
    assert fld.value == "测试乳"
    assert fld.evidence.quote == "测试乳"


def test_field_aliases():
    assert _field("配料表：水、大豆\n", "ingredients").value == ["水", "大豆"]
    assert _field("生产者：某乳业\n", "producer_name").value == "某乳业"
    assert _field("制造商：某乳业\n", "producer_name").value == "某乳业"
    assert _field("联系方式：400-000-0000\n", "producer_contact").value == "400-000-0000"
    assert _field("联系电话：400-000-0000\n", "producer_contact").value == "400-000-0000"
    assert _field("执行标准：GB/T 20981\n", "product_standard").value == "GB/T 20981"
    assert _field("生产许可证编号：SC12345678901234\n", "sc_license").value == "SC12345678901234"
    assert _field("保质期至：2027年03月12日\n", "expiry_date").value == "2027-03-12"


def test_longest_alias_wins_expiry_over_shelf():
    # 「保质期到期日」不得被「保质期」吞掉
    card = parse_label("保质期到期日：2027年01月16日\n保质期：6个月\n")
    assert card.get("expiry_date").value == "2027-01-16"
    assert card.get("shelf_life").value == {"value": 6, "unit": "个月"}


def test_first_occurrence_wins():
    card = parse_label("食品名称：第一个名\n食品名称：第二个名\n")
    assert card.get("food_name").value == "第一个名"


def test_failed_line_allows_retry():
    # 首行值不可析 → 记 unresolved；次行可析 → 成功
    card = parse_label("净含量：计量称重\n净含量：250 mL\n")
    assert card.get("net_content").value == {"amount": 250.0, "unit": "mL"}
    assert card.unresolved, "失败行应留 unresolved 提示"


# --- 净含量 -------------------------------------------------------------------

def test_net_content_units_and_spec():
    assert _field("净含量：200g\n", "net_content").value == {"amount": 200.0, "unit": "g"}
    assert _field("净含量：250 mL\n", "net_content").value == {"amount": 250.0, "unit": "mL"}
    assert _field("净含量：500毫升\n", "net_content").value == {"amount": 500.0, "unit": "mL"}
    assert _field("净含量：1.5L\n", "net_content").value == {"amount": 1.5, "unit": "L"}
    fld = _field("净含量：200g×5包\n", "net_content")
    assert fld.value == {"amount": 200.0, "unit": "g", "spec": "×5包"}
    assert fld.evidence.quote == "200g"


def test_net_content_unparsable_goes_unresolved():
    card = parse_label("净含量：计量称重\n")
    assert not card.has("net_content")
    assert any("净含量" in u for u in card.unresolved)


# --- 保质期 -------------------------------------------------------------------

def test_shelf_life_value_unit():
    assert _field("保质期：21天\n", "shelf_life").value == {"value": 21, "unit": "天"}
    assert _field("保质期：18个月\n", "shelf_life").value == {"value": 18, "unit": "个月"}
    assert _field("保质期：2年\n", "shelf_life").value == {"value": 2, "unit": "年"}
    assert _field("保质期：12日\n", "shelf_life").value == {"value": 12, "unit": "天"}


# --- 日期：V7a 三种非规范格式都必须解析出日期值（M2 契约） ---------------------

def test_production_date_formats():
    assert _field("生产日期：2026年09月12日\n", "production_date").value == "2026-09-12"
    assert _field("生产日期：2026年9月12日\n", "production_date").value == "2026-09-12"
    assert _field("生产日期：2026.9.12\n", "production_date").value == "2026-09-12"
    assert _field("生产日期：2026/9/12\n", "production_date").value == "2026-09-12"
    assert _field("生产日期：2026-09-12\n", "production_date").value == "2026-09-12"
    assert _field("生产日期：20260912\n", "production_date").value == "2026-09-12"


def test_nonstandard_date_quote_is_shown_text():
    fld = _field("生产日期：2026.9.12\n", "production_date")
    assert fld.evidence.quote == "2026.9.12"


def test_invalid_date_values_go_unresolved():
    card = parse_label("生产日期：2026年13月40日\n")
    assert not card.has("production_date")
    assert any("生产日期" in u for u in card.unresolved)


def test_packing_and_filling_date_aliases():
    assert _field("包装日期：2026年01月02日\n", "production_date").value == "2026-01-02"
    assert _field("灌装日期：2026年01月02日\n", "production_date").value == "2026-01-02"


# --- 配料 ---------------------------------------------------------------------

def test_ingredients_split_and_strip():
    fld = _field("配料：水、 白砂糖 ，柠檬酸\n", "ingredients")
    assert fld.value == ["水", "白砂糖", "柠檬酸"]
    assert fld.evidence.quote == "水、 白砂糖 ，柠檬酸"


# --- 营养成分表 ----------------------------------------------------------------

NUTRI_BLOCK = (
    "营养成分表\n"
    "项目\t每100g\tNRV%\n"
    "能量\t363kJ\t4%\n"
    "蛋白质\t2.8g\t5%\n"
    "糖\t10.5g\t—\n"
)


def test_nutrition_table_rows():
    card = parse_label("食品名称：测试乳\n" + NUTRI_BLOCK)
    rows = card.nutrition_table
    assert [r["name"] for r in rows] == ["能量", "蛋白质", "糖"]
    assert rows[0]["amount"] == 363 and rows[0]["unit"] == "kJ" and rows[0]["nrv_percent"] == 4
    assert rows[1]["amount"] == 2.8 and rows[1]["nrv_percent"] == 5
    assert rows[2]["nrv_percent"] is None  # 糖无 NRV →「—」
    assert all(r["per_serving"] is False for r in rows)
    assert all(r["evidence"]["quote"] in NUTRI_BLOCK for r in rows)


def test_nutrition_table_per_serving_header():
    card = parse_label("营养成分表\n项目\t每份\tNRV%\n能量\t100kJ\t1%\n")
    assert card.nutrition_table[0]["per_serving"] is True


def test_malformed_row_ends_table_with_unresolved():
    card = parse_label("食品名称：测试乳\n" + NUTRI_BLOCK + "异常行\t没有单位\tx%\n声称：无糖\n")
    assert len(card.nutrition_table) == 3
    assert any("无法解析的表行" in u for u in card.unresolved)
    assert card.claims == ["无糖"]


# --- 提示语与声称 ---------------------------------------------------------------

def test_salt_oil_sugar_notice_field():
    card = parse_label("食品名称：测试乳\n儿童青少年应避免过量摄入盐油糖。\n")
    fld = card.get("salt_oil_sugar_notice")
    assert fld.value is True
    assert fld.evidence.quote == "儿童青少年应避免过量摄入盐油糖。"
    assert fld.evidence.region == "营养成分表"


def test_salt_oil_sugar_notice_absent_is_not_unresolved():
    card = parse_label("食品名称：测试乳\n")
    assert not card.has("salt_oil_sugar_notice")
    assert not any("盐油糖" in u for u in card.unresolved)


def test_claims_multiple_lines():
    card = parse_label("声称：无糖\n声称：高钙\n")
    assert card.claims == ["无糖", "高钙"]
    assert card.get("claims").value == ["无糖", "高钙"]
    assert card.get("claims").evidence.quote == "无糖"


# --- unresolved 纪律 -------------------------------------------------------------

def test_all_missing_mandatory_reported():
    card = parse_label("")
    joined = "\n".join(card.unresolved)
    for label in ("食品名称", "配料", "净含量", "生产日期", "保质期", "贮存条件",
                  "生产商", "地址", "联系方式", "食品生产许可证编号", "营养成分表"):
        assert label in joined, f"缺提示：{label}"
    assert not card.fields


def test_legally_absent_fields_not_unresolved():
    # 保质期到期日（2011 语义合法缺失）/产品标准代号（视情形）/声称/提示语缺失不进 unresolved
    card = parse_label("食品名称：测试乳\n净含量：1g\n生产日期：2026年09月12日\n"
                       "保质期：6个月\n贮存条件：常温\n生产商：某厂\n地址：某地\n"
                       "联系方式：400-000-0000\n食品生产许可证编号：SC12345678901234\n")
    assert not any("到期日" in u for u in card.unresolved)
    assert not any("标准代号" in u for u in card.unresolved)
    assert not any("声称" in u for u in card.unresolved)


def test_allergen_notice_parsed_and_quality_grade_unresolved():
    """M4：致敏物质提示为正式字段（value=True/缺位，D19 同款）；质量等级仍为非 P0 提示。"""
    text = "食品名称：测试乳\n致敏原提示：含小麦制品\n质量等级：一级\n"
    card = parse_label(text)
    fld = card.get("allergen_notice")
    assert fld is not None and fld.value is True
    assert fld.evidence.quote == "致敏原提示：含小麦制品"
    assert text[fld.evidence.span[0]:fld.evidence.span[1]] == fld.evidence.quote
    joined = "\n".join(card.unresolved)
    assert "致敏原提示" not in joined
    assert "质量等级" in joined
    assert "allergen_notice" not in card.unresolved_detail


def test_allergen_notice_wording_variants():
    """引导词变体（D.2.2 字面子集）：致敏物质提示/致敏物质/致敏原信息均解析。"""
    assert _field("致敏物质提示：含乳。\n", "allergen_notice").value is True
    assert _field("致敏物质：含大豆蛋白。\n", "allergen_notice").value is True
    assert _field("致敏原信息：本生产线也加工含小麦制品。\n", "allergen_notice") is not None
    assert _field("本品含乳制品\n", "allergen_notice") is None  # 无引导词不解析（防误挂）


# --- 证据与镜像一致性 ------------------------------------------------------------

def test_crlf_input_spans_clean():
    text = "食品名称：测试乳\r\n净含量：1g\r\n"
    card = parse_label(text)
    fld = card.get("food_name")
    assert fld.evidence.quote == "测试乳"
    assert text[fld.evidence.span[0]:fld.evidence.span[1]] == "测试乳"


def test_mirror_lists_consistent():
    card = parse_label("配料：水、白砂糖\n声称：无糖\n")
    assert card.ingredients == card.get("ingredients").value == ["水", "白砂糖"]
    assert card.claims == card.get("claims").value == ["无糖"]
