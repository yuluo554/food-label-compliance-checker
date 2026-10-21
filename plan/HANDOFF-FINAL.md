# HANDOFF-FINAL —— 项目收尾快照（M6 收尾 + 发布完成，2026-10-04）

> 项目已走完"计划→数据→解析→规则→基准→交付→发布"全链并公开发布。本文件为终态快照，
> 无后续里程碑；历史交接见 HANDOFF-M1–M6（均已标注过时仅作历史）。
>
> **2026-10-21 追加：M6 后做过一次二次迭代并发布 v0.7.0（见文末 §5）。§1–§4 保留为 v0.6.0 时点的事实快照，不改写。**

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
- 数据台账唯一开放项：GB/T 8170 数值修约总则核对（`data/knowledge/raw/retrieval-log.md` 待办）——不影响发布与指标，留待后续 Contributor。**（2026-10-21 起该开放项已登记复核锚：`nutrient_reference.json` 的 `rounding.reviewed_at=2026-10-04` / `next_review=2027-10-04` / `open_item`；《食品安全法》项同见 `data/README.md`。）**
- 演示物即时生成不入仓：docx 报告由 `check --report` 即时生成；冻结 fixtures 之外批量生成物走 `--out` 临时目录。

## 5. 二次迭代 v0.7.0（2026-10-21，M6 后追加）

> 本节是 **v0.6.0 之后**的新事实，不代表 §1–§4 被改写（那两节是 2026-10-04 的快照）。逐项门禁与负控见 [RELEASE-0.7.0.md](RELEASE-0.7.0.md)。

- **来源与决策**：M6 后一轮只读审计给出 12 条缺陷（D1–D12）；用户拍板 DEC-1=A（V6 契约收口）/ DEC-2=A（sdist 定性）/ DEC-3=A（floor 3.12 + PEP 639）/ DEC-4=B（发 0.7.0）。
- **修掉的机制缺陷（D1/D5）**：`bench e2e` 的 `detection_rate=1.0` 此前只在冻结集 `seed=2026` 成立——`beverage-tea` 声明支持 V6，但规则 `ING-ORDER-01` 的 `only_if=["果汁饮料"]` 不覆盖茶饮料品名，注入真值永远检不出（15 个种子里 11 个掉到 0.875~0.9）。**去掉该模板的 V6 声明**后 15/15 seed 全 1.0；**冻结集 14 文件逐字节未变**（两个判据：磁盘 sha256 + manifest 登记值）。新增跨 seed 守门测试，负控实测 9/15 seed 红。
- **支持面（D3/D8/D9/D10）**：`requires-python` `>=3.8` → **`>=3.12`**；PEP 639 + `setuptools>=77`；CI 矩阵 `["3.12"]`（腿数 4→2）；actions v4/v5 → **v7**（Node20 弃用注解清零）。硬约束：**PEP 639 与 `>=3.8` 不可兼得**（PEP 639 需 setuptools>=77，后者需 Python≥3.9）。
- **发布形态（D2）**：sdist 定性为「非交付物」，只发 wheel，并在 pyproject 与 README 双处披露（此前"装了包但自带测试全红"无人知）。
- **文档与复核锚（D4/D6/D11）**：规则条数统一为 21+26=**47 条**（历史 HANDOFF 只加括注）；`nutrient_reference.json` 的 `rounding` 增 `status_scope`（显式声明 `status="已核对"` 的覆盖范围、排除 GB/T 8170）、`open_item` 与复核锚。
- **四类人工一致性变机判（D12 + 本轮主动补）**：版本单一来源守门、跨 seed bench 守门、复核锚守门、README 计数守门（**四者均做了负控**）。
- **实测**：pytest **191 → 198 项全绿**（本机 dev / GitHub 全新 clone+全新 venv / CI 两条腿，三处一致）；bench parse F1=1.0；脱敏四扫全 0。
- **发布**：提交 `e6e5896`，tag `v0.7.0`（**tag 打在代码提交上、零滞后**，与 v0.6.0 把 tag 打在含留档的收尾提交上不同，见 D25）+ Release 3 附件（whl 94,441 / tar.gz 122,151 / SHA256SUMS 228），**附件三方 sha256 逐字符一致**、下载件与本地构建件**逐字节相同**；CI 两个 run（push main + push tag）4 个 job 全 success。**未上传 PyPI**；v0.6.0 的 Release 未动。
- **残留**：1 条第三方弃用警告（Starlette `httpx`→`httpx2`，属 extras 范畴，未动）；`ubuntu-latest` 自 2026-10-19 起迁 Ubuntu 26 的迁移 notice（本轮通过时仍是 24.04）。
- **发布期三条可复用教训**：① 改 JSON 文案用英文引号会破语法（必须跑一次 `json.load`）；② push 成功 ≠ CI 已触发（本次延迟约 10 分钟，判据是 `actions/runs?head_sha=` 的 `total_count` 变 1）；③ `setuptools` 构建字节不可复现但内容可复现——**不要把「字节复现」当发布门判据**。
- **当前状态**：包已发（Release 可下、CI 绿、附件可自证），二次迭代本身的**独立复验**尚未进行；复验方最该重做的五件事见 RELEASE-0.7.0 §10。
