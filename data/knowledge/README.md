# data/knowledge —— 法规知识库（三层）

> 纪律（ai-tool-project-sprint 阶段3）：无出处的值不得以确定语气落库或写进结论；每条入库挂{标准号+条号+渠道}；查不到显式标"待核对"并继续推进。

## 三层结构

| 层 | 目录 | 内容 | 入仓策略 |
|---|---|---|---|
| L1 原文 | `raw/` | 标准官方文本（GB 7718-2011/2025、GB 28050-2011/2025 等）+ 渠道登记 | 按许可情况决定全文或要点摘录入库；来源台账必登 |
| L2 条文块 | `blocks/` | 按"块号+条款号+原文摘录+出处+status"切分的条文块 | 入仓 |
| L3 机器规则 | `src/food_label_checker/rules/rulesets/*.json` | 引擎消费的规则表（basis 挂回 L2 出处） | 随包分发 |

## 目录

- `raw/` —— M1 起入库：四部标准官方 PDF + `_extracted/` 提取文本（PyMuPDF，重提取命令见 tools/build_blocks.py）+ 渠道台账
- `blocks/` —— M3 已填充：4 部标准 428 块（块号=条款号，`basis.quote_ref` 引用格式 `<file_id>.json#<条款号>`；守门 tests/test_blocks.py）
- `rules/` —— 规则来源台账（M3）

## status 取值约定

- `已核对`：挂有官方原文出处（标准号+条号+渠道），结论允许确定语气；
- `待核对`：尚未挂原文，结论自动带"依据待核对"标注（引擎 `flagged_pending_basis` 强制置位）。

M3 现状：规则集 45 条全部 `已核对`（挂条文块 quote_ref）；仍开放的待核对项为 GB/T 8170 修约总则与《食品安全法》文本（见 data/README.md 查证记录）。
