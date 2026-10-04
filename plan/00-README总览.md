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
| [06-决策记录.md](06-决策记录.md) | 重大决策表（D01–D18，随里程碑滚动追加） | ✅ 持续更新 |
| HANDOFF-M1.md | 跨会话交接快照（M0 收尾，已过时仅作历史） | ✅ 2026-10-04 |
| HANDOFF-M2.md | 跨会话交接快照（M1 收尾，当前有效） | ✅ 2026-10-04 |

## 决策记录

权威决策表见 [06-决策记录.md](06-决策记录.md)（D01–D18）。要点：命名 D06（dist=仓库名/包 `food_label_checker`/CLI `flcheck`）、核心零依赖 D07、LLM 走 OpenAI 兼容默认关闭 D08、git 身份已切 noreply D11、发布走 SSH（token 无 workflow scope）D12、真值语义与 V→规则契约 D16、标准原文官方渠道入库与 nutrient_reference 升"已核对" D17、fixtures 冻结策略 D18。

## 里程碑（初稿→详设见 plan/05，含各里程碑 DoD）

- **M0 计划定稿 + 可运行骨架 ✅（2026-10-04）**：plan/00–06 齐全；`pip install -e .` 可装；垂直切片通电（CLI 对最小双标尺规则集跑通 JSON 审查）；pytest 全绿；CI/README/LICENSE/.gitattributes 就绪
- **M1 数据先行 ✅（2026-10-04）**：datagen 生成器（4 品类 8 模板 + V1–V8 注入器 + 真值 JSON，固定 seed 位级复现）；`flcheck gen` 落地；冻结 fixtures（seed 2026/n 12）+ 复现/EOL 守门测试；四部标准官方原文 PDF 入库（sppt.cfsa.net.cn 官方渠道）；NRV/能量系数/无糖阈值/声称白名单逐项挂原文核对（nutrient_reference.json 升"已核对"）；数据台账登记齐全
- M2 解析层：标签解析器 → 标签参数卡（含营养成分表结构化），回归测试
- M3 知识与规则：双标尺规则集（2011/2025 versioned）+ 数值复算引擎 + 声称阈值表，依据关联
- M4 LLM 兜底 + 内置基准：解析 F1 ≥0.95、误报 0
- M5 编排与交付：CLI + docx 审查报告 + Web 面板（0 外链）
- M6 脱敏发布 GitHub + 收尾固化（tag/release/topics）
