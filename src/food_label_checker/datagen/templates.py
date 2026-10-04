"""datagen 品类模板与标签渲染：4 品类 8 小类模板（干净版基线）+ 语料渲染器。

模板只定义物理合理的内容（虚构品牌、真实品类、自洂数值）；能量与 NRV% 由
nutrients.py 按待核对系数/基准值计算，保证干净版自洽（clean_baseline）。
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .nutrients import compute_energy, nrv_value

GENERATION_YEAR = 2026  # 固定生成年份（不读时钟，保证位级复现）

# 营养表固定行序（2025 表1/示例4 顺序：能量/蛋白质/脂肪/饱和脂肪/碳水/糖/钠）；
# NRV% 不适用的营养素（糖）标 "—"
_ROW_ORDER = ("能量", "蛋白质", "脂肪", "饱和脂肪", "碳水化合物", "糖", "钠")
_NUTRIENT_UNIT = {
    "能量": "kJ", "蛋白质": "g", "脂肪": "g", "饱和脂肪": "g",
    "碳水化合物": "g", "糖": "g", "钠": "mg",
}
# 2025 §4.5 强制提示语（营养成分表下方标示；M3 契约：2011 规则集不得对其报不合规）
SALT_OIL_SUGAR_NOTICE = "儿童青少年应避免过量摄入盐油糖。"


@dataclass
class Template:
    key: str                    # 机器名（用于文件名）
    category: str               # 品类中文名
    name: str                   # 食品名称
    brand: str                  # 虚构品牌
    producer: str
    address: str
    phone: str
    sc_license: str
    product_standard: str
    net_amount: float
    net_unit: str
    ingredients: List[str]      # 正确递减序
    over2_prefix: int           # 前 N 个配料占比 >2%（V6 只在前缀内相邻互换）
    nutrition_basis: str        # 每100g / 每100mL
    nutrients: Dict[str, float] # 蛋白质/脂肪/碳水化合物/[糖]/钠
    storage: str
    shelf_value: int
    shelf_unit: str             # 个月 / 天
    v_supported: tuple          # 该模板支持的注入类型（V1 恒支持）


TEMPLATES: List[Template] = [
    Template(
        key="dairy-sterilized-milk", category="乳制品", name="灭菌乳（全脂）", brand="牧云",
        producer="牧云乳业有限公司", address="云溪省云溪市食品工业园 8 号", phone="400-810-0001",
        sc_license="SC10532050001234", product_standard="GB 25190",
        net_amount=250, net_unit="mL",
        ingredients=["生牛乳"], over2_prefix=0, nutrition_basis="每100mL",
        nutrients={"蛋白质": 3.2, "脂肪": 3.6, "饱和脂肪": 2.1, "碳水化合物": 4.8, "钠": 55},
        storage="常温避光保存，不得暴晒", shelf_value=6, shelf_unit="个月",
        v_supported=("V1", "V2", "V3", "V5", "V7", "V8"),
    ),
    Template(
        key="dairy-fermented", category="乳制品", name="发酵乳（原味）", brand="牧云",
        producer="牧云乳业有限公司", address="云溪省云溪市食品工业园 8 号", phone="400-810-0001",
        sc_license="SC10532050001235", product_standard="GB 19302",
        net_amount=200, net_unit="g",
        ingredients=["生牛乳", "白砂糖", "保加利亚乳杆菌", "嗜热链球菌"], over2_prefix=2,
        nutrition_basis="每100g",
        nutrients={"蛋白质": 2.8, "脂肪": 3.0, "饱和脂肪": 1.8, "碳水化合物": 12.0, "糖": 10.5, "钠": 65},
        storage="2℃～6℃冷藏保存", shelf_value=21, shelf_unit="天",
        v_supported=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"),
    ),
    Template(
        key="beverage-juice", category="饮料", name="苹果汁饮料", brand="沁原",
        producer="沁原饮品有限公司", address="蓝川省蓝川市高新食品园 66 号", phone="400-820-0002",
        sc_license="SC10633010002222", product_standard="GB/T 31121",
        net_amount=500, net_unit="mL",
        ingredients=["水", "苹果汁", "白砂糖", "柠檬酸", "维生素C", "食用香精"], over2_prefix=3,
        nutrition_basis="每100mL",
        nutrients={"蛋白质": 0.4, "脂肪": 0, "饱和脂肪": 0, "碳水化合物": 10.5, "糖": 9.8, "钠": 20},
        storage="常温避光保存，开启后需冷藏并尽快饮用", shelf_value=9, shelf_unit="个月",
        v_supported=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"),
    ),
    Template(
        key="beverage-tea", category="饮料", name="柠檬味红茶饮料", brand="沁原",
        producer="沁原饮品有限公司", address="蓝川省蓝川市高新食品园 66 号", phone="400-820-0002",
        sc_license="SC10633010002223", product_standard="GB/T 21733",
        net_amount=500, net_unit="mL",
        ingredients=["水", "白砂糖", "红茶茶叶", "食用香精"], over2_prefix=3,
        nutrition_basis="每100mL",
        nutrients={"蛋白质": 0.2, "脂肪": 0, "饱和脂肪": 0, "碳水化合物": 4.5, "糖": 4.2, "钠": 15},
        storage="常温避光保存，开启后需冷藏并尽快饮用", shelf_value=12, shelf_unit="个月",
        v_supported=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"),
    ),
    Template(
        key="bakery-bread", category="烘焙", name="早餐切片面包", brand="禾序",
        producer="禾序食品有限公司", address="青禾省青禾市烘焙产业园 12 号", phone="400-830-0003",
        sc_license="SC10434010003333", product_standard="GB/T 20981",
        net_amount=300, net_unit="g",
        ingredients=["小麦粉", "水", "白砂糖", "鸡蛋", "食用植物油", "酵母", "食用盐"],
        over2_prefix=4, nutrition_basis="每100g",
        nutrients={"蛋白质": 8.2, "脂肪": 5.5, "饱和脂肪": 1.2, "碳水化合物": 45.0, "糖": 6.0, "钠": 320},
        storage="置阴凉干燥处，避免阳光直射", shelf_value=7, shelf_unit="天",
        v_supported=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"),
    ),
    Template(
        key="bakery-biscuit", category="烘焙", name="苏打饼干", brand="禾序",
        producer="禾序食品有限公司", address="青禾省青禾市烘焙产业园 12 号", phone="400-830-0003",
        sc_license="SC10434010003334", product_standard="GB/T 20980",
        net_amount=205, net_unit="g",
        ingredients=["小麦粉", "食用植物油", "白砂糖", "全脂乳粉", "碳酸氢钠", "食用盐", "酵母"],
        over2_prefix=3, nutrition_basis="每100g",
        nutrients={"蛋白质": 7.5, "脂肪": 12.0, "饱和脂肪": 5.5, "碳水化合物": 68.0, "糖": 15.0, "钠": 580},
        storage="存放于阴凉干燥处，避免受潮", shelf_value=10, shelf_unit="个月",
        v_supported=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"),
    ),
    Template(
        key="condiment-soy-sauce", category="调味品", name="酿造酱油", brand="鼎醇",
        producer="鼎醇调味食品有限公司", address="酱湖省酱湖市酿造园区 5 号", phone="400-840-0004",
        sc_license="SC10335010004444", product_standard="GB/T 18186",
        net_amount=500, net_unit="mL",
        ingredients=["水", "脱脂大豆", "小麦粉", "食用盐", "白砂糖", "酵母提取物"],
        over2_prefix=3, nutrition_basis="每100mL",
        nutrients={"蛋白质": 7.0, "脂肪": 0.2, "饱和脂肪": 0, "碳水化合物": 4.0, "糖": 2.0, "钠": 950},
        storage="阴凉避光保存，开封后冷藏", shelf_value=18, shelf_unit="个月",
        v_supported=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"),
    ),
    Template(
        key="condiment-vinegar", category="调味品", name="酿造食醋", brand="鼎醇",
        producer="鼎醇调味食品有限公司", address="酱湖省酱湖市酿造园区 5 号", phone="400-840-0004",
        sc_license="SC10335010004445", product_standard="GB/T 18187",
        net_amount=500, net_unit="mL",
        ingredients=["水", "高粱", "麸皮", "大米", "食用盐", "白砂糖"], over2_prefix=3,
        nutrition_basis="每100mL",
        nutrients={"蛋白质": 1.0, "脂肪": 0, "饱和脂肪": 0, "碳水化合物": 3.5, "钠": 520},
        storage="阴凉干燥处避光保存", shelf_value=24, shelf_unit="个月",
        v_supported=("V1", "V2", "V3", "V5", "V6", "V7", "V8"),
    ),
]

CATEGORY_TEMPLATES: Dict[str, List[Template]] = {}
for _t in TEMPLATES:
    CATEGORY_TEMPLATES.setdefault(_t.category, []).append(_t)

CATEGORY_ALIASES = {
    "乳制品": "乳制品", "dairy": "乳制品",
    "饮料": "饮料", "beverage": "饮料",
    "烘焙": "烘焙", "bakery": "烘焙",
    "调味品": "调味品", "condiment": "调味品",
}


def resolve_categories(spec: Optional[str]) -> List[str]:
    """把 --categories 取值（中文/英文别名，逗号分隔）解析为品类列表。None → 全部。"""
    if spec is None or not spec.strip():
        return list(CATEGORY_TEMPLATES)
    cats: List[str] = []
    for token in spec.split(","):
        cat = CATEGORY_ALIASES.get(token.strip())
        if not cat:
            raise ValueError(
                f"未知品类：{token.strip()}（可选：乳制品/饮料/烘焙/调味品 或 dairy/beverage/bakery/condiment）"
            )
        if cat not in cats:
            cats.append(cat)
    return cats


def build_nutrition_rows(t: Template) -> List[Dict[str, Any]]:
    """按模板数值构建自洽营养表：能量=折算修约，NRV%=round(amount/NRV×100)，糖 NRV 缺省"—"。"""
    protein = t.nutrients.get("蛋白质", 0.0)
    fat = t.nutrients.get("脂肪", 0.0)
    carb = t.nutrients.get("碳水化合物", 0.0)
    amounts: Dict[str, float] = dict(t.nutrients)
    amounts["能量"] = compute_energy(protein, fat, carb)

    rows: List[Dict[str, Any]] = []
    for name in _ROW_ORDER:
        if name not in amounts:
            continue
        amount = amounts[name]
        unit = _NUTRIENT_UNIT[name]
        if name != "糖":  # 糖无 NRV（两版表A.1 均未设，已核对）
            nrv = round(nrv_value(name, float(amount), unit) * 100)
        else:
            nrv = None
        rows.append({"name": name, "amount": amount, "unit": unit, "nrv_percent": nrv})
    return rows


def add_months(d: date, months: int) -> date:
    """月加法，日截断到月末（生成器约定，与 M3 date_logic 复算共用口径，待核对）。"""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last))


def compute_expiry(production: date, shelf_value: int, shelf_unit: str) -> date:
    """保质期到期日推算：月单位月加法、天单位按天加法（不做 -1 天修正，待核对）。"""
    if shelf_unit == "个月":
        return add_months(production, shelf_value)
    if shelf_unit == "天":
        return production + timedelta(days=shelf_value)
    raise ValueError(f"未知保质期单位：{shelf_unit}")


def fmt_amount(v: float) -> str:
    """整数化显示：269→'269'，3.2→'3.2'，12.0→'12'。"""
    if float(v) == int(v):
        return str(int(v))
    return f"{v:g}"


@dataclass
class LabelState:
    """可被注入器变异的标签状态；render_label 输出语料文本。"""

    template: Template
    production_date: date
    expiry_date: date                     # 推算的正确到期日
    ingredients: List[str] = field(default_factory=list)
    nutrition: List[Dict[str, Any]] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    deleted: set = field(default_factory=set)          # V1 删除的字段键
    nonstandard_date: Optional[str] = None             # V7a：生产日期标示原文
    shown_expiry_date: Optional[date] = None           # V7b：标示的到期日


def initial_state(t: Template, production_date: date) -> LabelState:
    return LabelState(
        template=t,
        production_date=production_date,
        expiry_date=compute_expiry(production_date, t.shelf_value, t.shelf_unit),
        ingredients=list(t.ingredients),
        nutrition=build_nutrition_rows(t),
    )


def render_label(state: LabelState) -> str:
    t = state.template
    d = state.deleted
    lines: List[str] = []
    if "food_name" not in d:
        lines.append(f"食品名称：{t.brand} {t.name}")
    if "ingredients" not in d:
        lines.append("配料：" + "、".join(state.ingredients))
    lines.append(f"产品标准代号：{t.product_standard}")
    if "net_content" not in d:
        lines.append(f"净含量：{fmt_amount(t.net_amount)}{t.net_unit}")
    if "production_date" not in d:
        shown = state.nonstandard_date or state.production_date.strftime("%Y年%m月%d日")
        lines.append(f"生产日期：{shown}")
    if "shelf_life" not in d:
        lines.append(f"保质期：{t.shelf_value}{t.shelf_unit}")
    shown_expiry = state.shown_expiry_date or state.expiry_date
    lines.append(f"保质期到期日：{shown_expiry.strftime('%Y年%m月%d日')}")
    if "storage_conditions" not in d:
        lines.append(f"贮存条件：{t.storage}")
    lines.append(f"生产商：{t.producer}（虚构演示数据）")
    lines.append(f"地址：{t.address}")
    lines.append(f"联系方式：{t.phone}")
    if "sc_license" not in d:
        lines.append(f"食品生产许可证编号：{t.sc_license}")
    lines.append("营养成分表")
    lines.append(f"项目\t{t.nutrition_basis}\tNRV%")
    for row in state.nutrition:
        nrv = f"{row['nrv_percent']}%" if row["nrv_percent"] is not None else "—"
        lines.append(f"{row['name']}\t{fmt_amount(row['amount'])}{row['unit']}\t{nrv}")
    # 2025 §4.5 强制提示语（营养成分表下方；M3 契约：2011 规则集不得对其报不合规）
    lines.append(SALT_OIL_SUGAR_NOTICE)
    for claim in state.claims:
        lines.append(f"声称：{claim}")
    return "\n".join(lines) + "\n"
