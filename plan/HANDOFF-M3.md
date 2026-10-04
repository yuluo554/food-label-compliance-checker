# HANDOFF-M3 —— 跨会话交接快照（M2 收尾，2026-10-04）

> **已过时仅作历史（M3 已完成，接续请读 HANDOFF-M4.md）。** 原始快照如下。

> 用法：新对话直接 `/goal 读取 "plan/HANDOFF-M3.md" 继续完成任务`。本快照先落盘再结束对话；M3 收尾后本文件头部标注"已过时仅作历史"，另写 HANDOFF-M4。

## 1. 当前进度（M0 ✅ + M1 ✅ + M2 ✅）

- plan/00–06 齐全且已回写（06 含 D01–D19；04/05 有 M2 变更记录）
- 包 `food_label_checker` v0.3.0，CLI `flcheck`；pytest **67 项全绿**（0.9s 全离线）
- **M2 交付**：解析器全字段落地 `src/food_label_checker/parser/text_parser.py`——
  - P0 全字段：food_name / ingredients / net_content / production_date / shelf_life / expiry_date / storage_conditions / producer_name+address+contact / sc_license / product_standard / nutrition_table（三列制表符，行级证据）/ claims / salt_oil_sugar_notice（增补字段，2025 §4.5 提示语在位性）
  - 证据挂全：每字段与营养行带 Evidence（区域+逐字摘录+span），quote 必为输入逐字子串且 text[span]==quote 逐字节对应（测试锁定）
  - V7a 契约：非规范日期（点/斜杠/连字符/紧凑 8 位）解析出 ISO 日期值，quote=原样标示；不得误报缺生产日期
  - 冻结集 12 样本逐字段值全等回归 + F1 自测 **1.0**（TP=240/FP=0/FN=0，门槛 0.9）
  - `flcheck parse <file>` 输出参数卡 JSON（实测通过）；datagen 增补 `generate_dataset_with_states`（输出位级不变）
- 冻结 fixtures `data/generated/frozen/seed-2026-n12/` 未动（M2 只读；重生成守门测试仍绿）

## 2. M3 待办（知识与规则，DoD 详见 plan/05 §2 M3）

1. 四部标准条文块入库 `data/knowledge/blocks/`（块号+条款号+原文摘录+出处+status，从 raw/ PDF 切分）
2. 规则集 2011/2025 双版本 JSON 扩库（目标合计 ≥40 条，M3 收尾盘点），每条 basis 挂原文条款、status=已核对/待核对
3. 9 种 check_type 引擎全通（mandatory_field 已有；format/nrv_recalc/energy_consistency/ingredient_order/claim_threshold/claim_whitelist/date_logic/conditional），未知类型仍转"待人工确认"
4. 数值复算引擎 numeric/：NRV% 复算（修约间隔 1）/能量折算（17/37/17，容差按表2 实际≤120%标示值）/声称阈值（无糖 ≤0.5g/100g(mL)）/日期逻辑（生产+保质期 vs 到期日）
5. 类目门控 only_if 全类型生效（test_engine_dual 已锁定该性质，M3 扩门控词表并回归）
6. dual_diff 对照输出已有骨架，随规则库补对照回归

## 3. 既定口径清单（动了会打挂基准/测试，先对照再动手）

- **真值语义/语料格式/V→规则契约（D16）**：权威口径在 `src/food_label_checker/datagen/__init__.py` 模块注释——主期望+also_expect、评测按"全部非 pass 集合"对账、clean_baseline=双标尺零不合规、误报=未被真值覆盖的 fail
- **V 主期望 rule_id（M3 规则库硬约束，D16）**：MAND-NAME/ING/NET/SHELF/DATE/STORAGE/SC-01、NRV-RECALC-01、ENERGY-CONSIST-01、CLAIM-THRESH-01、CLAIM-ZEROADD-01（仅 2025，2011 不得报）、ING-ORDER-01、FMT-DATE-01、DATE-LOGIC-01、CLAIM-FUNC-01；另有 M0 骨架已入 rulesets 的 MAND-EXPIRY-01（2025，param=expiry_date）
- **解析层字段契约（D19，M3 必须遵守）**：全部 P0 键在 card.fields（mandatory_field 的 param 以此命名：food_name/ingredients/net_content/production_date/shelf_life/storage_conditions/sc_license/expiry_date…）；card.ingredients/claims 为镜像列表；nutrition_table 顶层列表，行 dict 含 name/amount/unit/nrv_percent/per_serving/evidence；日期字段 value=ISO、原样标示在 evidence.quote（FMT-DATE-01 判格式直接对 quote 正则 `\d{4}年\d{2}月\d{2}日`，DATE-LOGIC-01 对 value 做 ISO 日期运算）；单位已归一（g/mL/L/kg、天/个月）；salt_oil_sugar_notice 字段 value=True/缺位
- **2011 豁免契约**：2011 规则集不得对"儿童青少年应避免过量摄入盐油糖。"提示语或自愿性营养行（饱和脂肪/糖等 2025 新增强制项）报不合规；2025 强制标示 7 项（能量/蛋白/脂肪/饱和脂肪/碳水/糖/钠）+ 提示语（§4.1/§4.5）
- **到期日推算口径（生成器约定，date_logic 复算必须一致）**：保质期到期日 = 生产日期 + 保质期；月单位月加法且日截断到月末、天单位按天加法——共用 `templates.add_months/compute_expiry`，不得另写一套
- **能量容差**：按表2（实际 ≤120% 标示值，两版一致）；V3 注入纯低报（shown=0.5–0.75×correct）；干净样本能量=round(17P+37F+17C)（修约），ENERGY-CONSIST-01 容差须容纳 ±1 kJ 修约
- **数值唯一出处**：rules/nutrient_reference.json（status=已核对，随包分发）；无出处不落库，basis.status 两值（已核对/待核对）；flagged_pending_basis 引擎自动置位（勿在规则 JSON 手写）
- **指标门槛**：解析 F1≥0.95（M4 全量）、误报 0（不放宽）；M2 自测口径与助手见 tests/parse_f1.py（D19 ④）
- **门控纪律**：only_if 对全部 check_type 生效（test_engine_dual 锁定）；规则集枚举 `AVAILABLE_RULESETS` 与 rulesets/*.json 一一对应（test_rulesets_dir_matches_available 锁定），新增规则集必须同步该元组
- **结论三级**：合规/不合规/待人工确认；未知 check_type 转"待人工确认"不崩溃
- **CLI 退出码**：0=审查完成（含检出不合规），2=用法/输入错误
- **0 外链**：webapp docs_url/redoc_url 必须 None（测试锁定）；测试全离线，LLM 一律 mock
- **复现纪律（D16/D18）**：模板/生成器/冻结集任一侧变更 → 重生成冻结集并升 DATAGEN_VERSION（守门测试强制暴露）；M3 若新增对干净样本适用的规则，同步模板与冻结集

## 4. 本机环境坑（仅记实测）

- 本机 Python 3.8.8（`py` 启动器；`python` 是商店占位符），跑脚本带 `PYTHONDONTWRITEBYTECODE=1`；3.8 无 `Path.write_text(newline=)`（写文件用 open(..., newline="\n")）
- `flcheck.exe` 装在 `...\Python38\Scripts\`（不在 PATH）——用 `py -m food_label_checker` 或 `py -X utf8` 等价；GBK 控制台已做 errors=replace 兜底
- pip 曾被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`
- gh 已登录 `yuluo554`，token scopes 无 `workflow` → **建仓推送必须走 SSH**（D12）
- Git Bash `/tmp` 与 Windows Python 路径不通；临时文件用工作区相对路径
- 卫健委官网主站有瑞数 WAF（curl/WebFetch 412）：需真实浏览器；检索平台 sppt.cfsa.net.cn:8086 是 HTTPS，附件走表单 POST（raw/retrieval-log.md 有可直接复用的 curl 命令参数）——M3 切条文块时用

## 5. M2 DoD 对照（逐项）

- [x] 文本解析器覆盖参数卡字段表全部 P0 字段（§1.1 全表 + salt_oil_sugar_notice 增补）
- [x] 证据（区域+逐字摘录+span）挂全；quote⊆输入且 text[span]==quote 逐字节对应；V7a 非规范日期解析出日期值、不误报缺生产日期
- [x] 每解析器配生成器样例回归测试（冻结集 12 样本只读全等回归 + 字段级变体单元测试；期望值生成器内存重建）
- [x] 解析 F1 自测（冻结集）= 1.0 ≥ 0.9；`flcheck parse` 输出参数卡 JSON
- [x] pytest 67 项全绿（新增 29 项：frozen 回归 5 + 字段单元 24；重写 1 项 hint 测试为已解析断言）

## 6. 关键命令速查

```bash
# 安装与测试（仓库根目录）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q

# 解析演示（M2 演示物）
py -X utf8 -m food_label_checker parse examples/sample_label.txt
py -X utf8 -m food_label_checker parse data/generated/frozen/seed-2026-n12/sample-0011-bakery-biscuit.txt  # V7a 非规范日期
py -X utf8 -m food_label_checker check examples/sample_label.txt --ruleset both

# 生成器（冻结集重生成必须升 DATAGEN_VERSION 并跑守门测试）
py -X utf8 -m food_label_checker gen --seed 2026 --n 12 --out data/generated/frozen --force

# F1 自测单独跑
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests/test_parser_frozen.py::test_parse_f1_frozen_at_least_090 -q -s

# git（本仓库身份已配好，勿改 user.email）
git log --format="%h %ae %ce" --all   # 应只见 282769740+yuluo554@users.noreply.github.com
```
