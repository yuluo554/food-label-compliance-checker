# food-label-compliance-checker 项目计划总览

**项目**：预包装食品标签合规智能审查系统（食品安全领域）
**方法论**：ai-tool-project-sprint（plan 先行 → 数据先行 → 解析/规则/LLM → 基准 → 编排交付 → 脱敏发布）
**项目系列**：construction-drawing-plan-checker（建造，已发布）→ power-operation-ticket-checker（电力）→ medical-record-quality-checker（医疗）→ bidding-document-checker（公共采购）→ 本项目（食品，题目定稿）

## 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [01-题目详细定义.md](01-题目详细定义.md) | 模拟赛题全文（介绍/任务/提交材料/评分/含金量锚点/边界） | ✅ 定稿 2026-10-04 |
| [02-需求解读.md](02-需求解读.md) | 痛点→能力转译表、FR/NFR 清单、边界与非目标、评分验收口径 | ✅ 2026-10-04 |
| [03-架构与技术选型.md](03-架构与技术选型.md) | 分层架构、技术栈、依赖分层 extras 契约、目录结构 | ✅ 2026-10-04 |
| [04-模块详设.md](04-模块详设.md) | 参数卡 schema、规则集 schema、数值复算引擎、双标尺、基准设计 | ✅ 2026-10-04 |
| [05-数据计划与里程碑.md](05-数据计划与里程碑.md) | 数据四类目录、标准原文获取计划、生成器设计、M0–M6 DoD | ✅ 2026-10-04 |
| [06-决策记录.md](06-决策记录.md) | 重大决策表（D01–D22，随里程碑滚动追加） | ✅ 持续更新 |
| HANDOFF-M1.md | 跨会话交接快照（M0 收尾，已过时仅作历史） | ✅ 2026-10-04 |
| HANDOFF-M2.md | 跨会话交接快照（M1 收尾，已过时仅作历史） | ✅ 2026-10-04 |
| HANDOFF-M3.md | 跨会话交接快照（M2 收尾，已过时仅作历史） | ✅ 2026-10-04 |
| HANDOFF-M4.md | 跨会话交接快照（M3 收尾，已过时仅作历史） | ✅ 2026-10-04 |
| HANDOFF-M5.md | 跨会话交接快照（M4 收尾，当前有效） | ✅ 2026-10-04 |

## 决策记录

权威决策表见 [06-决策记录.md](06-决策记录.md)（D01–D21）。要点：命名 D06（dist=仓库名/包 `food_label_checker`/CLI `flcheck`）、核心零依赖 D07、LLM 走 OpenAI 兼容默认关闭 D08、git 身份已切 noreply D11、发布走 SSH（token 无 workflow scope）D12、真值语义与 V→规则契约 D16、标准原文官方渠道入库与 nutrient_reference 升"已核对" D17、fixtures 冻结策略 D18、M2 解析层字段与值形态契约 D19、M3 知识与规则落地口径（能量系数 2011 无条款挂 2025 出处、日期格式/配料序/豁免的确定性近似）D20/D21。

## 里程碑（初稿→详设见 plan/05，含各里程碑 DoD）

- **M0 计划定稿 + 可运行骨架 ✅（2026-10-04）**：plan/00–06 齐全；`pip install -e .` 可装；垂直切片通电（CLI 对最小双标尺规则集跑通 JSON 审查）；pytest 全绿；CI/README/LICENSE/.gitattributes 就绪
- **M1 数据先行 ✅（2026-10-04）**：datagen 生成器（4 品类 8 模板 + V1–V8 注入器 + 真值 JSON，固定 seed 位级复现）；`flcheck gen` 落地；冻结 fixtures（seed 2026/n 12）+ 复现/EOL 守门测试；四部标准官方原文 PDF 入库（sppt.cfsa.net.cn 官方渠道）；NRV/能量系数/无糖阈值/声称白名单逐项挂原文核对（nutrient_reference.json 升"已核对"）；数据台账登记齐全
- **M2 解析层 ✅（2026-10-04）**：文本解析器覆盖参数卡 P0 全字段（含营养成分表三列制表符结构化 + 盐油糖提示语在位性 + 声称行），证据（区域+逐字摘录+span）挂全且 span 与 quote 逐字节对应；V7a 非规范日期解析出日期值不误报缺生产日期；冻结集 12 样本逐字段值回归 + F1 自测 1.0（≥0.9 达标）；`flcheck parse` 输出参数卡 JSON；pytest 67 项全绿
- **M3 知识与规则 ✅（2026-10-04）**：四部标准条文块入库（428 块，块号=条款号，`tools/build_blocks.py` 可复现切分 + 守门测试）；双标尺规则集扩库 2011×21 + 2025×24 = 45 条（DoD ≥40），全部挂条文块 quote_ref、status=已核对；9 种 check_type 引擎全通（含 conditional 豁免分支、行级多结论、not_run 语义）；数值复算引擎（NRV%/能量折算/声称阈值/日期逻辑，系数挂 2025 §2.3，D20 补录 2011 无对应条款）；门控词表定稿并对全类型回归；冻结集 12 样本双标尺全量对账（干净零不合规、注入精确命中）+ dual_diff 对照回归；pytest 113 项全绿
- **M4 基准与 LLM 兜底 ✅（2026-10-04）**：内置基准 `flcheck bench parse`（冻结集字段级 **F1=1.0**，TP=253/FP=0/FN=0，门槛 ≥0.95）与 `flcheck bench e2e`（**检出率 1.0（9/9）、误报 0**、dual_diff 零违例），评测器迁入 src（对账口径=D16 全部非 pass 集合，D21 等价迁移）；LLM 兜底适配器（默认关闭，quote⊆原文逐字校验+值从摘录重解析，不可达自动降级，25 项 mock 测试零真实 API）；M3 推迟项联动落地（D22）：2025 规则集 26 条共 47 条（+NUTR-ROWS-01 营养行完整性、+ALLERGEN-01 致敏物质提示，均挂条文块）、check_type 11 种、DATAGEN_VERSION 1→2 冻结集重生成；行在值不可析转"待人工确认"降级语义；pytest 159 项全绿
- M5 编排与交付：CLI + docx 审查报告 + Web 面板（0 外链）
- M6 脱敏发布 GitHub + 收尾固化（tag/release/topics）
