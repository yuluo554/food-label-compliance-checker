# food-label-compliance-checker

预包装食品标签合规智能审查系统——面向 GB 7718/GB 28050 换版期（新版标准 2025-03-27 发布、2027-03-16 强制实施）的标签审查开源工具：把文本标签解析为结构化"参数卡"，用**双标尺规则引擎**分别按 GB 7718-2011（现行）与 GB 7718-2025（过渡期）审查，输出"现行合规 / 新规不合规"对照，每条结论挂标准条款出处与标签原文证据。

> **项目状态：🚧 基准与 LLM 兜底（M4）**。垂直切片、**合成标签生成器**（固定 seed 位级复现 + V1–V8 违规注入真值）、**全量文本解析**（参数卡全字段 + 逐字证据）、**全量双标尺规则引擎**（47 条规则挂官方原文、11 种检查类型、数值复算）、**内置评测基准**（`flcheck bench`，解析 F1=1.0 / 误报 0）与 **LLM 兜底适配器**（默认关闭，quote 逐字校验防幻觉）已真实可跑；条文块知识库（四部标准 428 块）已入库挂出处。报告/Web（M5）按 [plan/05](plan/05-数据计划与里程碑.md) 里程碑推进。规划中的能力见下文"特性"，**请勿将未标注"已实现"的内容当作可用功能**。

## 特性

**已实现（M0 骨架 → M1 数据先行 → M2 解析层 → M3 知识与规则 → M4 基准与 LLM 兜底）**

- 标签参数卡统一中间表示（字段-值-单位-置信度-证据），证据含标签区域+原文逐字摘录+字符偏移；全 P0 字段解析（配料表、三列制表符营养成分表行级证据、双日期、SC 号、声称、盐油糖提示语与致敏物质提示在位性等），非规范日期也解析出 ISO 值不误报
- **双标尺规则引擎（47 条规则）**：`gb7718-2011`（21 条）与 `gb7718-2025`（26 条，含保质期到期日、盐油糖提示语、"不添加"类受限声称、强制营养行完整性、致敏物质提示等 2025 新增）跑同一标签，输出 `dual_diff`（新增/消除的不合规项）
- **11 种检查类型全通**：强制标示 / 格式 / NRV% 复算 / 能量折算 / 配料递减序 / 声称阈值 / 声称用语 / 日期逻辑 / 条件豁免（conditional）/ 营养行完整性 / 致敏物质提示；未知类型显式转"待人工确认"
- **数值复算引擎**（`numeric/`，纯确定性）：NRV% 复算（修约间隔 1，容差 ±1）、能量折算（17/37/17 kJ/g，表2 低报 ≤120% 方向 + ±1 kJ 修约容差）、声称阈值（无糖 ≤0.5g/100g(mL) 等，阈值表挂原文）、到期日自洽（生产日期+保质期，与生成器共用同一推算实现）
- **内置评测基准（`flcheck bench`，零 API 依赖可复现）**：`bench parse` 字段级 P/R/F1（冻结集 12 样本 **F1=1.0**，TP=253/FP=0/FN=0，门槛 ≥0.95）；`bench e2e` 双标尺违规对账（**检出率 1.0、误报 0、dual_diff 零违例**，对账口径=全部非 pass 集合，D16/D21）；`flcheck bench parse && flcheck bench e2e` 一键复现
- **LLM 兜底适配器**（`llm/`，默认关闭）：OpenAI 兼容 REST（httpx，`FOOD_LABEL_LLM_*` 环境变量/.env 配置）、`enable_thinking=false`、候选行压缩；LLM 返回摘录必须 ⊆ 输入原文逐字校验、字段值从校验通过的摘录重新解析；不可达/超时/配置缺失自动降级规则通路（`check --llm`）；数值结论永远来自确定性规则
- **知识库三层**：L1 官方原文 PDF（sha256 台账）→ L2 条文块（428 块，块号=条款号，`tools/build_blocks.py` 可复现切分）→ L3 机器规则（每条 `basis.quote_ref` 挂回条文块，守门测试验证解析成立）
- 类目隔离门控（`only_if`，对全部检查类型生效）+ conditional 豁免分支（食醋/食用盐/味精/固态食糖豁免保质期与到期日标示，酒类转人工核验度数）
- 结论三级判定（合规 / 不合规 / 待人工确认），每条挂标准号+条款号+条文块出处；"待核对"规则自动标"依据待核对"；标示行存在但解析失败的情形转"待人工确认"而非误判不合规
- **合成标签生成器**（`flcheck gen`）：4 品类 8 模板，固定 seed 位级复现（DATAGEN_VERSION=2：全模板含 7 项营养行与致敏物质提示行），注入 V1–V8 已知违规并自动落真值 JSON（主期望+also_expect 语义）；冻结 fixtures 小集入仓 + 守门测试；冻结集 12 样本双标尺全量对账回归（干净样本零不合规、注入样本精确命中）
- CLI（`flcheck check / parse / gen / bench`）、CI（{ubuntu, windows} × {3.8, 3.11}）、全离线 pytest（159 项）

**规划中（按里程碑）**

- M5 docx 审查报告 + Web 面板（免构建、0 外链断网可演示）+ pipeline 状态机
- M6 脱敏发布 GitHub + 收尾固化（tag/release/topics）

## 架构

```mermaid
flowchart LR
    A[文本标签 .txt] --> B[解析层\n规则优先 LLM 兜底]
    B --> C[标签参数卡\n字段-值-单位-置信度-证据]
    C --> D[规则引擎\nversioned rulesets]
    R1[gb7718-2011] --> D
    R2[gb7718-2025] --> D
    D --> E[双标尺对照 dual_diff\n三级判定+条款出处]
    E --> F1[CLI flcheck]
    E --> F2[docx 报告 M5]
    E --> F3[Web 面板 M5]
```

核心通路（解析→参数卡→规则→判定）纯标准库实现，基准评测零 API 依赖可复现；web/report/llm 走可选依赖（extras）。

## 快速开始

```bash
git clone https://github.com/yuluo554/food-label-compliance-checker.git
cd food-label-compliance-checker

# Windows（py 启动器）                    # Linux / macOS
py -m venv .venv                        python3 -m venv .venv
source .venv/Scripts/activate           source .venv/bin/activate   # Git Bash
.venv\Scripts\activate                  # cmd.exe / PowerShell 用这行

python -m pip install -U pip
python -m pip install -e .

flcheck --version
flcheck check examples/sample_label.txt --ruleset both
```

`check` 输出（节选）：示例标签故意缺"净含量"、"营养成分表"，且缺新版要求的"保质期到期日"与"盐油糖提示语"——

```json
{
  "results": {
    "gb7718-2011": { "stats": { "checked": 15, "skipped": 2, "not_run": 4, "pass": 13, "fail": 2 }, "findings": [ ... ] },
    "gb7718-2025": { "stats": { "checked": 19, "skipped": 2, "not_run": 5, "pass": 15, "fail": 4 }, "findings": [ ... ] }
  },
  "dual_diff": { "baseline": "gb7718-2011", "target": "gb7718-2025", "new_fails": ["MAND-EXPIRY-01", "SALT-NOTICE-01"], "resolved_fails": [] }
}
```

## CLI

| 命令 | 状态 | 说明 |
|---|---|---|
| `flcheck check <file> --ruleset 2011\|2025\|both` | ✅ | 解析+审查，JSON 输出（退出码：0 审查完成 / 2 输入错误）；`--llm` 启用 LLM 兜底（默认关闭） |
| `flcheck parse <file>` | ✅ | 仅解析为标签参数卡 JSON |
| `flcheck gen --seed 42` | ✅ | 合成标签生成器：`--n`（默认 12：4 品类各 1 干净版 + V1–V8 各 1）/ `--categories` / `--out` / `--force`，输出标签文本 + truth.json + manifest.json（含 sha256） |
| `flcheck bench parse` / `flcheck bench e2e` | ✅ | 内置基准评测（零 API 依赖；退出码：0 达标 / 1 未达门槛 / 2 输入错误），`--data` 可指定数据集目录 |
| `flcheck web` | ⬜ M5 | Web 面板（0 外链） |

可选依赖：`pip install -e ".[web]"`（Web 面板）、`.[report]`（docx 报告）、`.[llm]`（LLM 兜底，默认关闭）、`.[dev]`（pytest）。

## LLM 兜底（默认关闭）

`llm/` 仅做非结构化抽取兜底（解析缺失字段的定位与原文摘录），**数值结论永远来自确定性规则**。防幻觉三闸：LLM 返回的摘录必须是输入原文的逐字子串、字段值从校验通过的摘录重新解析、抽取字段置信度 0.7 且输出标注 LLM 参与。不可达/超时/配置缺失自动降级到规则通路（`flcheck check` 退出码不变，`fallback` 字段报告原因）。

```bash
# OpenAI 兼容服务（示例为通配配置，二选一：环境变量或 cwd 下 .env 文件）
export FOOD_LABEL_LLM_ENABLED=1
export FOOD_LABEL_LLM_BASE_URL="https://api.deepseek.com/v1"   # 含 /v1
export FOOD_LABEL_LLM_API_KEY="sk-..."
export FOOD_LABEL_LLM_MODEL="deepseek-chat"
# 可选：FOOD_LABEL_LLM_TIMEOUT_SECONDS=30  FOOD_LABEL_LLM_MAX_RETRIES=2

flcheck check examples/sample_label.txt --ruleset both --llm
```

全部测试离线 mock（httpx.MockTransport/stub），CI 零真实 API 调用。

## 合成数据与复现（M1）

```bash
# 生成带真值数据集（默认 seed 42 / n 12 / 全品类）到 data/generated/seed-42-n12/
flcheck gen --seed 42
# 指定参数；目标已存在时需 --force 覆盖
flcheck gen --seed 2026 --n 24 --categories 乳制品,饮料 --out data/generated --force
```

- 每样本真值：`truth.json`（注入类型 V1–V8、主期望 `{rule_id, level}`、also_expect 双标尺期望）；`manifest.json` 记录全部文件 sha256；
- **位级可复现**：同参数重生成逐字节一致（真值语义与复现纪律见 `src/food_label_checker/datagen/__init__.py` 模块注释）；入仓冻结集 `data/generated/frozen/`（seed 2026/n 12）由 `tests/test_datagen_repro.py` 对照守门，生成器或冻结集任一侧漂移都会测试失败；
- 数值依据：NRV 基准值、能量系数（蛋白 17/脂肪 37/碳水 17 kJ/g）、无糖阈值等已对照官方原文核对（GB 28050-2011/2025），出处见 `src/food_label_checker/rules/nutrient_reference.json` 与 `data/knowledge/raw/retrieval-log.md`。

## 评测基准（M4 实测）

纯规则通路、零 API 依赖、固定 seed 数据集（冻结集 `seed-2026-n12`，DATAGEN_VERSION=2：4 品类各 1 干净版 + V1–V8 各 1 注入版）可复现。一键复现（退出码 0 = 达标）：

```bash
flcheck bench parse && flcheck bench e2e
# Windows 源码运行等价：py -X utf8 -m food_label_checker bench parse && py -X utf8 -m food_label_checker bench e2e
```

| 基准 | 指标 | 结果（2026-10-04 实测） |
|---|---|---|
| 标签解析（bench parse） | 字段级 P / R / F1 | P=1.0 / R=1.0 / **F1=1.0**（TP=253 / FP=0 / FN=0；DoD 门槛 F1 ≥ 0.95） |
| 端到端审查（bench e2e） | 检出率 / 误报率 | 检出率 **1.0**（真值 9 项主期望全部命中）/ 误报 **0**（17 个 fail 结论实例全部被真值覆盖；clean_baseline 零不合规、dual_diff 零违例、待人工确认 0） |

对账口径（D16/D21）：按"全部非 pass（不合规）集合"对账——真值每项主期望至少被一把标尺检出（检出率），标尺每个不合规结论必须被真值覆盖（误报）；also_expect 的 present_in/absent_in 按字面执行；"待人工确认"不参与对账；干净样本承诺两把标尺零不合规。评测器实现：`src/food_label_checker/bench/`。

## 项目结构

```
├── plan/                      # 计划文档（00 总览 / 01 题目 / 02 需求 / 03 架构 / 04 详设 / 05 里程碑 / 06 决策）
├── data/                      # 数据台账（样例标签 / 标准原文 / 条文块 / 规则来源）
├── src/food_label_checker/    # 源码（src 布局）
│   ├── parser/                # 文本标签 → 参数卡
│   ├── rules/                 # 规则引擎 + rulesets/*.json（随包分发）
│   ├── numeric/  datagen/  llm/  report/  webapp/   # 按里程碑实现
│   └── cli.py  pipeline.py  models.py
├── tests/                     # 全离线 pytest（含失败路径）
└── examples/                  # 演示标签
```

## 限制

- 示例与评测标签**全部为合成数据**，品牌虚构（如"牧云"），不针对任何真实产品；
- 规则库覆盖 47 条已挂原文条款，但配料递减序采用"品类先验对"近似、豁免判定用关键词近似、致敏物质检索仅覆盖配料表、日期格式按项目口径从严判定（见 plan/06 决策记录）——确定性规则无法覆盖的形态会转"待人工确认"而非强行给结论，**当前输出不作为合规依据**；
- 输入以文本版标签为主，包装照片 OCR 为远期加分项；
- 本工具**不构成**法律、监管或营养咨询意见（见免责声明）。

## 免责声明

本项目输出仅为自动化初筛参考，不替代市场监管部门认定、专业合规审核或法定检验；标准条款以官方发布文本为准。使用者应自行核验结论后决策，项目作者不对依此产生的后果承担责任。本项目定位为标签合规审查工具，不提供营养健康建议，不涉及产品真伪鉴定。

## 已知环境问题（Windows）

- 控制台为 GBK 编码时，建议 `py -X utf8 -m food_label_checker ...` 运行；CLI 已做输出兜底不崩溃，但个别字符可能显示为替代符；
- pip 若被系统代理污染（`https://127.0.0.1:7897` 类报错），用 `NO_PROXY="*" no_proxy="*" python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`；
- `pip install -e .` 需要较新 pip（README 已内置 `pip install -U pip` 前置行）。

## 开发

```bash
python -m pip install -e ".[dev,web,report]"
pytest -q
```

计划文档（题目定义/需求/架构/详设/里程碑/决策记录）见 [plan/00-README总览.md](plan/00-README总览.md)。

## License

[MIT](LICENSE)
