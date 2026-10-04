# HANDOFF-M4 —— 跨会话交接快照（M3 收尾，2026-10-04）

> 用法：新对话直接 `/goal 读取 "plan/HANDOFF-M4.md" 继续完成任务`。本快照先落盘再结束对话；M4 收尾后本文件头部标注"已过时仅作历史"，另写 HANDOFF-M5。

## 1. 当前进度（M0 ✅ + M1 ✅ + M2 ✅ + M3 ✅）

- plan/00–06 齐全且已回写（06 含 D01–D21；04/05 有 M3 变更记录）
- 包 `food_label_checker` v0.4.0，CLI `flcheck`；pytest **113 项全绿**（1.1s 全离线）
- **M3 交付**（知识与规则，双标尺核心）：
  - **条文块知识库**：`data/knowledge/blocks/` 四部标准 **428 块**（7718-2011×114 / 7718-2025×129 / 28050-2011×83 / 28050-2025×102），块号=条款号，`tools/build_blocks.py` 从 PDF 提取文本（`raw/_extracted/` 随仓）可复现切分；tests/test_blocks.py 守门（含关键数值条款去空白口径挂原文 + PDF sha256 一致性）
  - **规则集扩库 45 条**（DoD ≥40）：gb7718-2011×21 + gb7718-2025×24（含 2025 新增：MAND-EXPIRY-01 到期日、SALT-NOTICE-01 盐油糖提示语、CLAIM-ZEROADD-01 "不添加"类受限声称）；全部 `basis.quote_ref` 挂条文块、status=已核对；D16 契约 rule_id 齐全且 2011 无 CLAIM-ZEROADD（豁免契约）
  - **9 种 check_type 引擎全通**：mandatory_field / format / nrv_recalc / energy_consistency / ingredient_order / claim_threshold / claim_whitelist / date_logic / conditional；处理器返回 Finding 列表（行级多结论）、None=not_run（前置缺失不产结论）；stats：pass+fail+manual==结论数、checked+skipped+not_run==规则总数；未知类型仍转"待人工确认"
  - **数值复算引擎 `numeric/`**：NRV% 复算（修约间隔 1，容差 ±1）、能量折算（17/37/17，表2 低报方向：复算 >120%×标示+1kJ 判矛盾）、声称阈值（无糖 ≤0.5/低糖 ≤5/低钠 ≤120，机器可读表 `nutrient_reference.claim_thresholds`）、日期逻辑（到期日=生产+保质期，**共用 datagen.templates.compute_expiry**）；系数挂 GB 28050-2025 §2.3（D20：2011 全文确认无对应条款）
  - **conditional 豁免分支**：字段缺失时按 params 判定——manual_if_any（酒类）→待人工、exempt_if_any（食醋/食用盐/味精/固态食糖[/葡萄酒]）→豁免通过（2025 到期日豁免要求生产日期在场）、否则不合规
  - **门控词表定稿**：only_if 品类词（果汁饮料、发酵乳、酸乳）+ 豁免词表，对全类型生效回归锁定
  - **冻结集 12 样本双标尺全量对账回归**（tests/test_engine_m3.py，D21）：干净样本两把标尺零不合规、注入样本非 pass 集合与真值主期望**精确相等**、dual_diff 仅 V5 产生 new_fails=[CLAIM-ZEROADD-01]、冻结集无"待人工确认"结论——M4 bench e2e 的合格线已在 M3 固化
  - 演示实测：`flcheck check examples/sample_label.txt --ruleset both` → 2011 报 MAND-NET/NUTR-TABLE，2025 增报 MAND-EXPIRY/SALT-NOTICE，dual_diff.new_fails=[MAND-EXPIRY-01, SALT-NOTICE-01]
- 冻结 fixtures `data/generated/frozen/seed-2026-n12/` 未动（DATAGEN_VERSION 仍为 1）

## 2. M4 待办（LLM 兜底 + 内置基准，DoD 详见 plan/05 §2 M4）

1. **LLM 适配器** `llm/`（OpenAI 兼容 REST，httpx；`FOOD_LABEL_LLM_*` 环境变量/.env 读配置，默认关闭；enable_thinking=false；候选行压缩；逐字摘录子串校验——LLM 返回的 quote 必须 ⊆ 输入原文；不可达/超时降级到"待人工确认"；全部测试 mock，零真实 API 调用）
2. **bench parse**：`flcheck bench parse`（F1≥0.95 可重复跑通）——把 tests/parse_f1.py 的 M2 自测口径迁入 src 定稿全量口径（期望值仍只由 generate_dataset_with_states 内存重建，禁止语料反提）
3. **bench e2e**：`flcheck bench e2e`（误报 0，检出率达标）——对账口径按 tests/test_engine_m3.py 固化的语义迁入 src 评测器（全部非 pass 集合对账；also_expect absent_in/present_in 按字面；clean_baseline 零不合规；待人工不参与对账）
4. **指标写进 README 评测表**（解析 F1 / 检出率 / 误报率），`flcheck bench parse && flcheck bench e2e` 一键复现
5. **M3 推迟项联动**（可选但建议在本里程碑做）：2025 §4.1 七项营养行完整性规则 + §4.12 致敏物质提示规则——需模板补糖行（灭菌乳/食醋补 糖 0g）与致敏原提示行并**重生成冻结集 + 升 DATAGEN_VERSION=2**（守门测试强制暴露）；详见 data/knowledge/rules/README.md 待办
6. 既定口径清单固化进 HANDOFF-M5

## 3. 既定口径清单（动了会打挂基准/测试，先对照再动手）

- **真值语义/语料格式/V→规则契约（D16）**：权威口径在 `src/food_label_checker/datagen/__init__.py` 模块注释——主期望+also_expect、评测按"全部非 pass 集合"对账、clean_baseline=双标尺零不合规、误报=未被真值覆盖的 fail
- **V 主期望 rule_id（已全部入库并验证，D16）**：MAND-NAME/ING/NET/SHELF/DATE/STORAGE/SC-01、NRV-RECALC-01、ENERGY-CONSIST-01、CLAIM-THRESH-01、CLAIM-ZEROADD-01（仅 2025）、ING-ORDER-01、FMT-DATE-01、DATE-LOGIC-01、CLAIM-FUNC-01；另有 MAND-EXPIRY-01/SALT-NOTICE-01（2025）、FMT-DATE-02/ING-ORDER-02/NUTR-TABLE-01/MAND-STD-01/MAND-PRODUCER-01/MAND-ADDRESS-01/MAND-CONTACT-01
- **解析层字段契约（D19）**：全部 P0 键在 card.fields；card.ingredients/claims 为镜像列表；nutrition_table 顶层列表（行 dict 含 name/amount/unit/nrv_percent/per_serving/evidence）；日期字段 value=ISO、原样标示在 evidence.quote；单位已归一；salt_oil_sugar_notice value=True/缺位
- **知识层契约（D20，M4 新增规则的依据纪律）**：L1 raw/ PDF（sha256 台账）→ L2 blocks/ 条文块（428 块，`<file_id>.json#<条款号>`）→ L3 rulesets/*.json（basis.quote_ref 挂 L2）；"无出处不落库"由 tests/test_blocks.py + test_rulesets_schema.py 守门；新规则必须先有块再有规则
- **确定性近似口径（D20，动前先读 plan/06）**：日期格式按 `YYYY年MM月DD日` 从严判定（FMT-DATE params.pattern）；配料递减序=品类先验对（果汁饮料：水/苹果汁<白砂糖；发酵乳：生牛乳<白砂糖/食用香精）；豁免=关键词近似；到期日推算共用 datagen.templates
- **引擎口径（M3 定稿）**：处理器返回列表、None=not_run；stats 三恒等式；门控 only_if 对全类型生效；conditional 三分支；NRV% 容差 ±1；能量低报方向 >120%+1kJ；claims 空时阈值/白名单规则产 pass 结论
- **2011 豁免契约**：2011 规则集不得含 CLAIM-ZEROADD-01，不得对盐油糖提示语/2025 新增强制项报不合规
- **评测对账口径（D16/D21）**：按"全部非 pass 集合"对账；误报 0 不放宽；对账语义已固化为 tests/test_engine_m3.py（M4 迁入 src 时保持等价）
- **指标门槛**：解析 F1≥0.95（M4 全量）、误报 0
- **数值唯一出处**：rules/nutrient_reference.json（含机器可读 claim_thresholds）；flagged_pending_basis 引擎自动置位
- **CLI 退出码**：0=审查完成，2=用法/输入错误；0 外链；测试全离线，LLM 一律 mock
- **复现纪律（D16/D18）**：模板/生成器/冻结集任一侧变更 → 重生成冻结集并升 DATAGEN_VERSION（守门测试强制暴露）；M4 推迟项落地时必须走此流程

## 4. 本机环境坑（仅记实测）

- 本机 Python 3.8.8（`py` 启动器；`python` 是商店占位符），跑脚本带 `PYTHONDONTWRITEBYTECODE=1`；**3.8 无 `Path.write_text(newline=)`**（写文件用 open(..., newline="\n")，M3 两次踩到）
- `flcheck.exe` 装在 `...\Python38\Scripts\`（不在 PATH）——用 `py -m food_label_checker` 或 `py -X utf8` 等价；GBK 控制台已做 errors=replace 兜底
- pip 曾被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`
- 本机可用 PyMuPDF（fitz）/pypdf——**非运行期依赖**，仅 tools/build_blocks.py 数据准备用；核心通路保持纯 stdlib（D07）
- gh 已登录 `yuluo554`，token scopes 无 `workflow` → **建仓推送必须走 SSH**（D12）
- Git Bash `/tmp` 与 Windows Python 路径不通；临时文件用工作区相对路径
- 长命令偶发被中断（本机稳定性），重跑即可；关键命令输出先落盘再解析

## 5. M3 DoD 对照（逐项）

- [x] 四部标准条文块入库（挂出处）：428 块 + tests/test_blocks.py 守门（结构/sha256/关键数值挂原文/quote_ref 可解析）
- [x] 规则集 2011/2025 双版本 JSON：21+24=45 条 ≥40，全部挂 quote_ref、status=已核对；D16 契约 id 齐全（含 2011 无 CLAIM-ZEROADD 断言）
- [x] 9 种 check_type 引擎全通：conditional 含豁免/人工分支；未知类型转"待人工确认"（测试锁定）
- [x] 类目门控生效（含 conditional 分支）且回归测试锁定：tests/test_engine_m3.py 门控词表用例
- [x] 数值复算引擎全通、系数挂出处：numeric/ 四类复算 + 单元测试；系数/阈值/误差全部挂条文块原文（D20）
- [x] 每条 finding 挂依据，待核对项自动标注：flagged_pending_basis==（status≠已核对）测试锁定；当前 45 条全部已核对
- [x] 演示物：`flcheck check sample.txt --ruleset both` 双标尺对照 + dual_diff（README 示例输出已更新为实测值）

## 6. 关键命令速查

```bash
# 安装与测试（仓库根目录）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q

# M3 演示物
py -X utf8 -m food_label_checker check examples/sample_label.txt --ruleset both
py -X utf8 -m food_label_checker check data/generated/frozen/seed-2026-n12/sample-0009-dairy-fermented.txt --ruleset both  # V5：仅 2025 报 CLAIM-ZEROADD-01

# 生成器（冻结集重生成必须升 DATAGEN_VERSION 并跑守门测试）
py -X utf8 -m food_label_checker gen --seed 2026 --n 12 --out data/generated/frozen --force

# 条文块重建（仅 PDF 更换时需要；提取文本随仓在 raw/_extracted/）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/build_blocks.py

# F1 自测单独跑
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests/test_parser_frozen.py::test_parse_f1_frozen_at_least_090 -q -s

# git（本仓库身份已配好，勿改 user.email）
git log --format="%h %ae %ce" --all   # 应只见 282769740+yuluo554@users.noreply.github.com
```
