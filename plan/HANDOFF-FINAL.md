# HANDOFF-FINAL —— 项目收尾快照（M6 收尾 + 发布完成，2026-10-04）

> 项目已走完"计划→数据→解析→规则→基准→交付→发布"全链并公开发布。本文件为终态快照，
> 无后续里程碑；历史交接见 HANDOFF-M1–M6（均已标注过时仅作历史）。

## 1. 终态

- **公开仓库**：github.com/yuluo554/food-label-compliance-checker（public，MIT，D10）
  - tag `v0.6.0`（打在含发布收尾文档的提交上）+ GitHub Release（notes=评测指标/快速开始/extras/免责声明）
  - topics 6 个：compliance / food-label / food-safety / gb28050 / gb7718 / rules-engine（`gh api` 回读确认）
  - CI 四矩阵（ubuntu/windows × Python 3.8/3.11）绿；push 数与 run 数对账一致
- **包**：`food_label_checker` v0.6.0（src 布局），CLI `flcheck`；pytest **191 全绿**（189 + 2 平台守门，本机 + 干净 venv + GitHub clone 三环境）
- **指标**：bench parse **F1=1.0**（TP=253/FP=0/FN=0）、e2e **检出率 1.0（9/9）、误报 0**、dual_diff 零违例
- **发布门留档**：[RELEASE-M6.md](RELEASE-M6.md)——脱敏四步复核、三扫全 0（阳性对照前置）、干净环境验证（收集数对照 191=dev）、SSH 建仓推送、CI Windows cp1252 事件实录、tag 迁移、发布后复核
- **决策表**：D01–D23 全闭环（D15 经用户确认不投赛事；2026 两个候选窗口已截止）

## 2. 发布期实录要点（同类项目可复用）

- **CI Windows cp1252 崩溃**（RELEASE-M6.md §7）：`strftime` 非 ASCII 格式串按 locale 编码，GitHub windows-latest 直接 UnicodeEncodeError；Ubuntu glibc 直通字节、本机 GBK 可编中文——两环境测不出，"dev 绿 CI 挂"环境差异型。修复：`datagen.templates.fmt_cn_date` 手工格式化 + `tests/test_platform_guard.py` AST 双守门（src 禁 strftime 非 ASCII 格式串；src+tests 内建 open 强制 encoding=/二进制）。
- **脱敏**：`tools/scan_sensitive.py`（阳性对照 selftest 前置、模式占位化防字面值入史）；HANDOFF 用法行个人路径泄露经 filter-branch tree-filter 首推前全历史重写；PDF sha256 对台账。
- **干净环境验证**：本地 clone + 全新 venv 按 README 逐字（含 `pip -U pip` 前置行）+ pytest 收集数对照——extras"dev 绿但干净环境静默少跑"第三形态的最终防线。
- **建仓推送**（D12）：`gh repo create --source .`（不带 --push）→ `ssh -T` 验证 → `remote set-url` SSH → push 一次成（token 无 workflow scope）。
- **本机坑补充**（叠加 HANDOFF-M6 §4）：崩溃家族副作用——进程崩溃瞬间若在写 pyc 会留下坏 pyc，之后每次读取必崩且报错点漂移（本次实录：系统 stdlib `sre_parse` pyc 损坏致 venv 内 pytest 收集期 SystemError）；对策不变（清 `__pycache__`+`PYTHONDONTWRITEBYTECODE=1`），git 子进程链（如 filter-branch tree-filter 内调 py）也要带环境变量。

## 3. 关键命令（复跑）

```bash
# 全量测试（extras 全装；分批 ≤70）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e ".[dev,web,report]"
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q

# 指标复现（退出码 0=达标）
py -X utf8 -m food_label_checker bench parse
py -X utf8 -m food_label_checker bench e2e

# 脱敏三扫（阳性对照 selftest 前置）
py -X utf8 tools/scan_sensitive.py selftest
py -X utf8 tools/scan_sensitive.py tracked / history / messages
```

## 4. 遗留与备注

- 无未达成项（plan/05 M6 偏差说明：无）。
- 数据台账唯一开放项：GB/T 8170 数值修约总则核对（`data/knowledge/raw/retrieval-log.md` 待办）——不影响发布与指标，留待后续 Contributor。
- 演示物即时生成不入仓：docx 报告由 `check --report` 即时生成；冻结 fixtures 之外批量生成物走 `--out` 临时目录。
