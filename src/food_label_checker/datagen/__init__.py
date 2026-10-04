"""合成标签生成器（M1，plan/05 §1.3）——带真值合成标签 + V1–V8 已知违规注入。

================================================================================
真值语义（定稿于 M1，见下；评测对账口径一经定稿不得单方更改，决策见 plan/06）
================================================================================

1. 每个样本的真值写在数据集 truth.json 的 samples[] 里，schema：

   {
     "sample_id", "file", "seed", "rng_key", "generator_version",
     "category", "template", "clean_baseline": bool,
     "injections": [ { "type": "V1".."V8",
                       "main_expect": {"rule_id": str, "level": "不合规"},
                       "also_expect": [ ... ],
                       "detail": { ... 人读调试信息，评测对账不使用 } } ]
   }

2. 注入项记主期望 main_expect（{rule_id, level}，rule_id 是 M3 规则库契约，
   见下方 V→规则契约表）；同一注入隐含的其余结论记 also_expect。

3. also_expect 条目两种可对账形态 + 一种信息形态：
   - {"present_in_ruleset": <ruleset_id>, "rule_id": <id>}
     —— 该 rule_id 必须在指定规则集结果中非 pass；
   - {"absent_in_ruleset": <ruleset_id>, "rule_id": <id>}
     —— 该 rule_id 不得在指定规则集结果中非 pass（双标尺差异样例，如 V5）；
   - {"kind": "info", ...} —— 仅供人读/调试，评测对账不使用。

4. 评测对账口径（M4 bench e2e，按 plan/04 §6）：按"全部非 pass 集合"对账，
   而非单点命中——对每个启用规则集 r：
   (a) 检出：真值每个 main_expect.rule_id 至少在一个启用规则集的非 pass 集合出现；
   (b) 无误报：规则集 r 的非 pass 集合中每个 rule_id 必须被该样本真值
       （main_expect / also_expect present_in / 该真值隐含的同主期望规则）覆盖；
   (c) also_expect 的 absent_in_ruleset 按字面对账；
   (d) "待人工确认"不参与对账；clean_baseline=true 样本的非 pass 集合必须为空。
   注意：clean_baseline=true 的承诺对象是"生成器知识范围内全部规则通过"。M3 扩
   规则库时若新增对干净样本适用的规则，必须同步更新模板并重生成冻结 fixtures
   （DATAGEN_VERSION 加一），守门测试会强制暴露失配。

5. V 注入类型 → 主期望规则契约表（M3 规则库必须包含以下 rule_id，语义见 M3；
   条款号全部"待核对"，M3 挂原文后升级）：

   | 注入 | 语义                          | main_expect.rule_id     |
   |------|-------------------------------|-------------------------|
   | V1   | 缺强制标示项（删 1–3 项）      | 被删字段对应 MAND-*（见 injectors.DELETABLE_FIELDS）|
   | V2   | NRV% 算错（超容差）           | NRV-RECALC-01           |
   | V3   | 能量折算矛盾                  | ENERGY-CONSIST-01       |
   | V4   | 营养声称超阈值（"无糖"）      | CLAIM-THRESH-01         |
   | V5   | "零添加"类 2025 受限声称      | CLAIM-ZEROADD-01        |
   | V6   | 配料递减序错误（>2% 相邻互换）| ING-ORDER-01            |
   | V7   | 日期格式(a)/日期逻辑(b)       | FMT-DATE-01 / DATE-LOGIC-01 |
   | V8   | 功能声称白名单外              | CLAIM-FUNC-01           |

   其中 V5 的 also_expect 锁定双标尺差异：{"absent_in_ruleset": "gb7718-2011", ...}
   + {"present_in_ruleset": "gb7718-2025", ...}（2011 版不得因"零添加"声称报不合规，
   M3 建 2011 规则集时必须遵守）。

6. 语料格式约定（M2 解析器按此回归）：
   - 字段行 `键：值`（全角冒号）；配料 `配料：A、B、C`（顿号分隔）；
   - 营养成分表为三列制表符分隔：`项目<TAB>每100g(mL)<TAB>NRV%`，行序按 2025 表1/
     示例4：能量/蛋白质/脂肪/饱和脂肪/碳水化合物/糖/钠；糖无 NRV 标"—"（两版表A.1
     均未设糖 NRV，已核对）；
   - 营养成分表下方独立一行：`儿童青少年应避免过量摄入盐油糖。`（2025 §4.5 强制
     提示语，已核对）。M3 契约：2011 规则集不得对该提示语或自愿性营养行（饱和脂肪/
     糖等 2025 新增强制项）输出不合规——它们在 2011 下属自愿标示信息；
   - 声称独立成行 `声称：xxx`；
   - 规范日期格式 `YYYY年MM月DD日`（V7a 注入非常规范式；M2 契约：非规范日期仍须
     解析出日期值，格式问题由 FMT-DATE-01 处理，不得升级为"缺生产日期"误报）；
   - 保质期到期日 = 生产日期 + 保质期（月加法，日截断到月末；天单位按天加法）。
     该口径为生成器约定（GB 对到期日推算口径待核对），M3 date_logic 复算必须与
     本约定一致；
   - 所有干净样本含"保质期到期日"行（2025 版强制项，保证 clean_baseline 双标尺通过）。

7. 数值与原文核验状态（2026-10-04 已核对，原文 PDF 在 data/knowledge/raw/）：
   - NRV 基准值：能量 8400kJ/蛋白 60g/脂肪 60g(2011 记 ≤60)/饱和脂肪(酸) 20g/碳水
     300g/钠 2000mg——两版附录A 表A.1 逐项一致，已核对；
   - 能量系数：蛋白 17/脂肪 37/碳水 17 kJ/g（2025 §2.3 原文；2011 条款出处 M3 补录）；
     plan/04 原"60×碳水"为笔误，M1 修正为 17 并留变更记录；
   - NRV% = X/NRV×100、修约间隔 1（两版 A.2/A.3 已核对）；生成器修约 round()（五成双）；
   - 允许误差（表2，两版已核对）：能量/脂肪/饱和脂肪/钠/糖等"实际 ≤120% 标示值"。
     V3 据此只取低报方向（见 injectors.V3_FACTORS 注释）；V2 偏差 ≥3 个百分点，
     超出修约间隔 1 的任何合理容差；
   - 无糖阈值 ≤0.5g/100g(mL)（两版表C.1 已核对）；功能声称白名单（两版附录D 已核对，
     V8 所选均为白名单外的疾病类声称）。

8. 复现性纪律：
   - 数值唯一出处：rules/nutrient_reference.json（status=已核对，M1 原文核验后升级）；
   - 每样本 rng = random.Random(f"{seed}:{idx}")（str 种子走 sha512，跨 Python
     版本稳定）；只允许 choice/randint/randrange + 本包 _shuffle（Fisher-Yates
     自实现，不用 random.sample/shuffle 以规避跨版本实现漂移）；
   - 生成日期固定在 GENERATION_YEAR 年内、不读时钟；输出不含时间戳/绝对路径；
   - DATAGEN_VERSION 随样本真值与 manifest 落盘；M1 固定 seed 位级复现由
     tests/test_datagen_repro.py 守门（对照 data/generated/frozen/）。
================================================================================
"""
from __future__ import annotations

from .generator import DATAGEN_VERSION, dataset_to_json, generate_dataset, write_dataset

__all__ = ["DATAGEN_VERSION", "dataset_to_json", "generate_dataset", "write_dataset"]
