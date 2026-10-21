# RELEASE-0.7.0 —— 二次迭代发布留档（2026-10-21）

> v0.6.0（M6）之后的第一次实质迭代发布门逐项实录。
> 扫描工具：`tools/scan_sensitive.py`（可复跑）。纪律同 RELEASE-M6：本文件不含敏感模式字面值/假样值。
>
> **本轮的诊断/路线/提示词/执行记录不在本仓内**：`update/`（含本机绝对路径）已入 `.gitignore`，只留本文件作为公共留档。

## 0. 本轮定位与决策

v0.6.0 发布后，诊断方对仓库做了一轮只读审计（12 条缺陷 D1–D12），本轮按 4 个用户拍板的决策执行：

| 决策 | 结论 | 影响批次 |
|---|---|---|
| DEC-1 | **A**：`beverage-tea` 模板去掉 `"V6"` 支持声明 | 批次一 |
| DEC-2 | **A**：sdist 定性为「非交付物」，只发 wheel | 批次二 |
| DEC-3 | **A**：`requires-python >=3.12` + PEP 639 + actions v7 | 批次二 |
| DEC-4 | **B**：升 0.7.0 + tag + Release（3 附件） | 发布 |

## 1. 缺陷 → 处置对照

| 缺陷 | 严重度 | 处置 | 证据 |
|---|---|---|---|
| D1 `bench e2e` 检出率 1.0 只是 seed=2026 的抽样运气（15 个种子里 11 个掉到 0.875~0.9） | P1 | 去 `beverage-tea` 的 V6 声明；15 seed 全 1.0 | §2 门禁 a/b |
| D2 sdist 不自足（解包后端测试 19 failed + 33 errors） | P1 | 定性为非交付物并在 pyproject/README 双处披露 | §3 |
| D3 `>=3.8` 已 EOL 而最新 extras 集体要求 ≥3.10 | P1 | 抬到 `>=3.12`，README 写明理由 | §3 |
| D4 规则条数 5 处文档写「45 条」（两处同文件自相矛盾） | P2 | 统一为 47 条；历史 HANDOFF 只加括注 | §4 |
| D5 无任何测试断言「任意 seed 达标」 | P2 | 新增跨 seed 守门测试（含负控） | §2 门禁 b′ |
| D6 `rounding.status="已核对"` 与 `general_rule`「未单独核对」自相矛盾 | P2 | 增 `status_scope` 显式限定覆盖范围 + `open_item` + 复核锚；新增守门测试 | §4 |
| D7 顶层 `code/` 是空目录 | P2 | 删除（0 文件、未跟踪） | §5 |
| D8 extras 无上限，3.8 与 3.12 装到的框架差一个大版本且未披露 | P2 | 随 D3 消解；README 写明 3.12 实测线 | §3 |
| D9 classifiers 声明 3.12 但 CI 只跑 3.8/3.11 | P2 | CI 矩阵改 `["3.12"]` | §3 |
| D10 CI 1 条 Node20 弃用（checkout@v4 / setup-python@v5） | P2 | 升 `@v7`；注解 0 条 | §6 |
| D11 `nutrient_reference.json` 顶层 status 是聚合值，与逐条可能矛盾 | P2 | 随 D6 一并由 `status_scope` 收口 | §4 |
| D12 版本号两处手写且无一致性守门；`--version` 测试只断言含 "flcheck" | P2 | 新增版本单一来源守门 + CLI 断言补真实版本号 | §5 |

## 2. 批次一：V6 契约收口（DEC-1=A）

### 改了什么

`src/food_label_checker/datagen/templates.py`：`beverage-tea` 的 `v_supported` 由 `("V1"…"V8")` 改为去掉 `"V6"`（8 项 → 7 项），并加注释说明成因；其余 7 个模板的 `v_supported` 未动。

成因：规则 `ING-ORDER-01` 的 `only_if=["果汁饮料"]` 不覆盖「柠檬味红茶饮料」这一品名 → 门控不命中、规则被 skipped → 注入的真值 `main_expect` 永远检不出。

### 门禁 a：冻结集 14 文件 sha256 改前改后逐条相同

| 文件 | 字节 | sha256 |
|---|---|---|
| manifest.json | 1654 | `6ca8c4f93b00605c043480a8e6eff208389e652b7767d527486847065f650d14` |
| truth.json | 7594 | `594d7c596442017e38e6ae4f971cf67cae3a36ef751727c55c2a3c6da7370be5` |
| sample-0001-dairy-fermented.txt | 711 | `0ebde642bbd9af4f834795e3104008cfd8d2a5214d78453d54846cc27ddaecde` |
| sample-0002-beverage-juice.txt | 785 | `c34d7f5c18cf09449b169b192ecac04cdcd017c47692b4d268779407f479a0ab` |
| sample-0003-bakery-bread.txt | 752 | `4e8b3d8e37188a54254cc4d8bd52b628b86531e6361a3d44c95c7994d18b7bb1` |
| sample-0004-condiment-soy-sauce.txt | 743 | `5330ee5d6a6484f33187d6b26811391d1759809e6ddd2e984b44d5d417f8789a` |
| sample-0005-dairy-fermented.txt | 620 | `2cce20bcf2b653bbb4eadf2590ad898e5932de4bcfdcf29cd208094065384dfb` |
| sample-0006-beverage-tea.txt | 768 | `d28ce06f9a32efd83acd84d4cb14a378ff568f5ee2d3f51addd22588084c94bc` |
| sample-0007-bakery-bread.txt | 750 | `4204fa45f6f75441449f531299d0f0a406e48d8e57285a54d24ec6e8721e51a0` |
| sample-0008-condiment-soy-sauce.txt | 759 | `8253653a26f6144f80bde2289360decde782096ae2c833513f0984c3b7a6a7cd` |
| sample-0009-dairy-fermented.txt | 739 | `1613c7c21cb6fd22417702fc3176d20bb3309897274d12717b5c1f2030e04374` |
| sample-0010-beverage-juice.txt | 785 | `3e8c671bab8ea3e0a18114df18e7a6eca5068a975de8663efc631ae3474154bd` |
| sample-0011-bakery-biscuit.txt | 759 | `28bd3fc0261cfc4ce6bc8088549ab3cb22da0b586de8709db7aaf1b5bb3abe8a` |
| sample-0012-condiment-vinegar.txt | 739 | `2eab97b9c408279d0006f6798f03ff07208260c4eca3bfb0d3f2156b6e7fc775` |

**两个判据都用**（不让 manifest 自证）：14 文件磁盘 sha256 改前 == 改后；`manifest.json` 登记的 13 条与磁盘逐一比对 → `ok=13 bad=0`。干净 clone 第三次复验仍一致。

### 门禁 b：15 个 seed 全 1.0

seed 表 `1,2,3,4,5,6,7,8,9,10,11,12,42,99,2026`，逐个 `flcheck gen --seed S` → `flcheck bench e2e --data …`：

```
15 行 gen_rc=0 e2e_rc=0
逐 JSON：detection_rate=1.0  false_positives=0  issues=[]  passed=True   （15/15）
```

### 门禁 b′：新守门的负控

把 `"V6"` 临时塞回 `beverage-tea` 后只跑 `test_bench_e2e_gate_across_seeds`：

```
E  AssertionError: seed=1 detection_rate=0.8889 … issues=['sample-0010: 漏检 ING-ORDER-01（两把标尺均未报不合规）']
   seed=2 0.8889 / seed=3 0.9 / seed=4 0.9 / seed=6 0.9 / seed=8 0.9 / seed=9 0.9
   seed=11 0.875 / seed=42 0.875
1 failed
```
恢复后 `1 passed`。**负控红 9 个 seed**（诊断报告称 11 个——两者测量路径不同：诊断走 CLI 子进程 `gen`+`bench`，本负控在测试进程内直接 `generate_dataset`；**个数不可混引**，但两者都证明该缺陷会让多数 seed 不达标）。

新增测试：`tests/test_bench.py::test_bench_e2e_gate_across_seeds`。

## 3. 批次二：支持面与发布形态（DEC-3=A / DEC-2=A）

| 项 | 改前 | 改后 |
|---|---|---|
| `[build-system] requires` | `["setuptools>=61"]` | `["setuptools>=77"]` |
| `requires-python` | `">=3.8"` | `">=3.12"` |
| `license` | `{ text = "MIT" }` | `"MIT"` + `license-files = ["LICENSE"]`（PEP 639） |
| classifiers | 含 `License :: OSI Approved :: MIT License`、`3.8`、`3.11`、`3.12` | 删前三项，保留 `3.12` |
| CI 矩阵 | `["3.8", "3.11"]`（4 job） | `["3.12"]`（2 job） |
| CI actions | `checkout@v4` / `setup-python@v5` | `checkout@v7` / `setup-python@v7` |
| sdist 定位 | 未披露（装了包自带测试全红无人知） | pyproject 注释 + README「开发」段明确「只发 wheel，sdist 仅供源码阅读」 |

**硬约束（记住，不可兼得）**：PEP 639 的 `license = "MIT"` 需要 `setuptools>=77`，而 `setuptools>=77` 需要 Python ≥3.9 —— 所以「PEP 639 + `>=3.8`」不可能同时成立。本轮两条都选了才落到 3.12。

actions 版本已核实真实存在：`checkout` latest `v7.0.1`、`setup-python` latest `v7.0.0`。

### 门禁 a：构建零弃用警告

`python -m build --sdist --wheel --outdir … 2>&1 | grep -ci "deprecat"` → **`0`**。

### 门禁 b：wheel METADATA

```
Metadata-Version: 2.4
License-Expression: MIT
License-File: LICENSE
Requires-Python: >=3.12
```

### 门禁 c：干净 venv 装 wheel + 仓外中立目录

```
flcheck --version   rc=0
check               rc=0
gen --seed 42       rc=0
bench parse         rc=0
bench e2e           rc=0
```

### 门禁 d：`git status --porcelain` 无构建产物

改前实测 `?? build/`（`.gitignore` 无 `build/`、`dist/`，`git check-ignore build/x` → rc=1）。批次四补齐后：`mkdir -p build dist && touch build/x dist/y && git status --porcelain` → 两项均不出现；`git check-ignore build/x dist/y` → 两项都命中。

## 4. 批次三：文档口径统一 + 复核锚（D4 / D6 / D11）

### 规则条数：5 处「45 条」全部带上 47 括注

> 下表行号是**本轮改动当时**的行号。收尾回写在 `plan/00` 补了索引行（`RELEASE-0.7.0.md` 一行），其后所有行号 +1 —— 故 `plan/00` 的 M3 行由 `:35` 变 `:36`。**引用本表时请按内容匹配，不要按行号硬对。**

| 文件 | 处置 |
|---|---|
| `data/knowledge/README.md:24` | 直接改写为「规则集 47 条（gb7718-2011×21 + gb7718-2025×26）」（该行行号未变） |
| `plan/05-数据计划与里程碑.md:65` | 「21+24=45 条 ≥40」（M4 扩至 21+26=47 条，见本文档 M4「追加成果」行）（行号未变） |
| `plan/00-README总览.md:35`（**现为 :36**） | 「…= 45 条（DoD ≥40）（M4 扩至 21+26=47 条，见下条 M4）」 |
| `plan/HANDOFF-M4.md:11 / :57 / :61` | 三处**只追加括注**（历史交接快照，不改原文语气）（行号未变） |

`grep -rn "47 条" --include=*.md . | grep -v update/` → 29 行。规则集实况复核：`gb7718-2011` 21 条 / `gb7718-2025` 26 条（**规则未动**）。

### `nutrient_reference.json` 的 `rounding` 矛盾（D6 的真正成因）

D6 的本质不是「某个字段写错了」，而是 **`status` 的覆盖范围没写**：`status="已核对"` 到底覆盖 `nrv_percent_step`，还是也覆盖 `general_rule` 提到的 GB/T 8170？读者无从判断。

处置：
- 保留 `status: "已核对"`（NRV% 修约间隔确实已核对）
- 新增 **`status_scope`**：显式声明只覆盖 `nrv_percent_step` / `amount_step`，**不含** general_rule 所述的 GB/T 8170 总则
- 新增 **`open_item`**：`"GB/T 8170 数值修约总则条款核对"`
- 新增 **`reviewed_at: "2026-10-04"`** / **`next_review: "2027-10-04"`**
- `general_rule` 改写为明确的**例外声明**（保留「未单独核对」这个事实）
- `source` 对象同样挂 `reviewed_at` / `next_review` / `review_note`（GB 28050-2025 于 2027-03-16 强制实施，复核排在其后约 7 个月）
- `data/README.md`：《食品安全法》行补「预计复核：2027-03-16 后」；GB/T 8170 行指向复核锚

新增 `tests/test_review_anchor.py`（3 项）：日期合法性与 `next_review > reviewed_at`、`status_scope` 必须显式排除 8170 且 `open_item` 非空、**逾期只打印提示不改退出码**（日程问题不是代码缺陷）。

## 5. 批次四：把四类人工一致性变成机判（D7 / D12）

| 守门 | 抓什么 | 负控实测 |
|---|---|---|
| `tests/test_version_single_source.py`（2 项） | `pyproject.toml` 的 `[project].version` 与 `__version__` 不一致；版本号须为 `X.Y.Z`（tag 名 = `v<version>`，不带 `.dev`/`+local`） | 改 `__version__ = "9.9.9"` → **1 failed** |
| `tests/test_cli.py::test_version_flag`（改） | `--version` 输出不含真实版本号（原来只断言含 `"flcheck"`，版本错了也不红） | 同上 |
| `tests/test_bench.py::test_bench_e2e_gate_across_seeds`（新） | 非冻结集 seed 的检出率不达标 | 恢复 V6 → **9/15 seed 红** |
| `tests/test_readme_count.py`（1 项，本轮主动补） | README「全离线 pytest（N 项」≠ 实际收集数 | 改 `191` → **1 failed** |

另：
- 删除空目录 `code/`（删前核实 `find code -type f` → 0、`git ls-files code` → 0）
- `.gitignore`「Python」段补 `build/`、`dist/`；「运行产物」段补 `update/`（交接物含本机绝对路径，会被 `scan_sensitive.py` 的 `personal_path_token` 报出——本轮实测：本文件初稿引用该路径示意即触发 1 条命中，改为相对表述后归零）
- 版本号两处同步 `0.6.0` → **`0.7.0`**

> `test_readme_count.py` 不在本轮诊断的强制清单里，是执行方主动补的：本仓长期靠人工同步 README 的测试数（`grep -rn "191" tests/` 改前零命中），属于「数字漂移无守门」。

## 6. 批次五：干净环境全量复验 + CI

### 干净环境（GitHub 全新 clone + 全新 venv）

```bash
git clone git@github.com:yuluo554/food-label-compliance-checker.git verify-clone   # HEAD == e6e5896
py -3.12 -m venv .venv && .venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -e ".[dev,web,report]"
.venv/Scripts/python.exe -m pytest -q          # 198 passed, 1 warning in 12.26s
```

- 五条业务命令（`--version` / `check` / `bench parse` / `bench e2e`）全 `rc=0`，`flcheck 0.7.0`
- 跨 seed 复验 `1 / 42 / 99` → `rc=0` ×3
- 脱敏四扫：`selftest` 报出 5 类（api_key_literal / cn_mobile / email / kv_secret / personal_path_win）、`tracked` / `messages` / `history` 全 `TOTAL_HITS=0`
- 冻结集 14 文件 sha256 与 §2 表中值逐条一致
- **确认 `update/` 未进公共仓**（clone 后不存在）

### CI

| run | head | 触发 | 结论 |
|---|---|---|---|
| `39623552294` | `e6e5896` | push main（代码提交） | **success** |
| `39623810607` | `e6e5896` | push tag `v0.7.0` | **success** |
| `39625845696` | `6410ff5` | push main（收尾回写提交） | **success** |

job：
| job id | name | conclusion | 注解 |
|---|---|---|---|
| `119302960278` | `test (ubuntu-latest, 3.12)` | success | 1 条（Ubuntu 26 迁移 **notice**，非弃用） |
| `119302960592` | `test (windows-latest, 3.12)` | success | **0 条** |
| `119303881273` | `test (ubuntu-latest, 3.12)`（tag run） | success | 1 条（同上 notice） |
| `119303880887` | `test (windows-latest, 3.12)`（tag run） | success | **0 条** |
| `119310748837` | `test (ubuntu-latest, 3.12)`（回写 run） | success | 1 条（同上 notice） |
| `119310749135` | `test (windows-latest, 3.12)`（回写 run） | success | **0 条** |

日志实测：ubuntu `198 passed` / windows `198 passed`，两腿 `flcheck 0.7.0`。
**Node20 弃用注解 0 条**（改前 checkout@v4 腿有 1 条）。腿数 4 → 2。

> 回写提交 `6410ff5` 只改 `plan/` 与 `README.md`（不动代码），CI 仍完整跑一遍并绿——顺带证明回写没破坏任何东西。**这三次 run 都要看**：判「CI 没触发」的标准是 `actions/runs?head_sha=<sha>` 的 `total_count` 变 1（本轮又出现约 4 分钟的延迟，见 §8 坑 2）。

## 7. 发布（DEC-4=B）

| 项 | 值 |
|---|---|
| 版本 | `0.7.0`（`pyproject.toml` 与 `__init__.py` 同步，由守门测试证明） |
| 提交 | `e6e58963009176029634bb151f75bd823d0632e9`（父 `e661610`） |
| tag | `v0.7.0`（annotated，tag 对象 `8cceb5574c509e75c8775763e2f8302bf0f32a53` → 剥壳 `e6e5896`，**零滞后**） |
| Release | https://github.com/yuluo554/food-label-compliance-checker/releases/tag/v0.7.0 （Latest） |

### tag 位置（D25）

tag **打在代码提交 `e6e5896` 上**（附件由该树构建）。本文件与其余 `plan/` 回写落在 tag 之后的 main 提交上，**未重指 tag**。理由：不动已发布 ref；wheel/sdist 不含 `plan/`，附件与 tag 树代码的逐字节对应关系不受影响。与 v0.6.0（tag 打在含 `RELEASE-M6.md` 的收尾提交上）的做法不同，差异已记入 D25。

### 收尾回写清单（tag 之后的提交）

| 文件 | 改动 |
|---|---|
| `plan/RELEASE-0.7.0.md` | 本文件（新增） |
| `plan/00-README总览.md` | 索引补本文件行、`HANDOFF-FINAL` 状态改 2026-10-21、决策表范围 D01–D25、新增「二次迭代」一节 |
| `plan/05-数据计划与里程碑.md` | 二次迭代小节由「🟡 待复验」改「✅ 已发布」，补门禁/负控/发布/残留 |
| `plan/06-决策记录.md` | 追加 D24（二次迭代范围与口径）、D25（tag 位置与回写纪律）；D05 标注「已被 D24 替代」（保留原结论） |
| `plan/03-架构与技术选型.md` | 语言/打包/CI 三行加「当前状态（2026-10-21，D24）」括注，原选型理由保留 |
| `plan/HANDOFF-FINAL.md` | 头部加"2026-10-21 追加"注记；§4 的 GB/T 8170 遗留项补复核锚；新增 §5「二次迭代 v0.7.0」 |
| `README.md` | 首屏与「已发布（M6 / v0.7.0）」段补本文件链接 |

### 附件（3 个）与三方 sha256 对撞

| 文件 | 字节 | sha256 |
|---|---|---|
| `food_label_compliance_checker-0.7.0-py3-none-any.whl` | 94,441 | `e69b91c67a62b894b73325f431585750a9fc85811f44d4cbfe31bdefd66a4f55` |
| `food_label_compliance_checker-0.7.0.tar.gz` | 122,151 | `ea92422f52d04b65d1b17449330b6eb1d1c48cc2942a18bf8a72d99d199c783c` |
| `SHA256SUMS` | 228 | `9ff5bb7771f03bcef496e6bd66ed636846c8611d932b3f131f7225c8834b8a84` |

- 本地 `sha256sum` == GitHub API `digest` == **真下载** `sha256sum`，三处逐字符一致
- `sha256sum -c SHA256SUMS`（用**下载下来的** SHA256SUMS）→ 两行 `OK`，rc=0
- 下载件与本地构建件 `cmp` → **逐字节相同**
- `SHA256SUMS` 为标准格式（两空格分隔、无 `*`、末尾单 LF）

### 发布件自证

用**下载的 wheel** 在另一个全新 venv + 仓外中立目录装并跑五条命令 → 全 `rc=0`。

### 复现性口径（重要）

用 tag 树重新构建，与发布件**字节不同**（setuptools 写入构建时间戳），但**内容级完全相同**：

```
WHEEL: entries release=35 tag=35 only_release=[] only_tag=[] content_diff=[]
SDIST: files  release=64 tag=64 only_release=[] only_tag=[] content_diff=[]    （64 个文件成员；含目录共 78 条 tar 成员）
```

**结论：字节不可复现、内容可复现。不要把「字节复现」当发布门判据。**

## 8. 发布期踩到的三个坑（同类项目可复用）

1. **JSON 文案里用英文双引号会破语法**：写 `general_rule` 时用 `与"四舍六入五成双"等效` 直接让 `nutrient_reference.json` 非法 → `json.JSONDecodeError: Expecting ',' delimiter: line 38 column 195`，三个新测试全红。改中文引号『』后修复。**改 JSON 值后必须跑一次 `json.load`。**
2. **push 成功 ≠ CI 已触发**：`git push` 返回成功、`git ls-remote` 与 API 都能看到新提交，但 `gh run list` / `actions/runs` 在约 **10 分钟**内看不到新 run（`pushed_at` 也停在旧值）。判「CI 没触发」必须等 `actions/runs?head_sha=<sha>` 的 `total_count` 变成 1。
3. **tag push 会再触发一次 CI**：本轮 push main 与 push tag 各产生一个 run（同一 head sha），两次都要看。

## 9. 范围边界与残留

**未做**：
- 本仓从未上传 PyPI（本轮也未传）
- `v0.6.0` 的 Release 未改动（仍是 0 附件）
- `plan/RELEASE-M6.md` 里 3.8 环境的描述未改（历史发布实录）
- 未改动任何 `rulesets/*.json` 的 id / check_type / basis / only_if / params / severity / advice，未动任何判定阈值，未动冻结集字节，未动 4 份国标 PDF 与 428 个条文块，未改 `tools/build_blocks.py` 切分逻辑，未动 LLM 兜底「默认关闭」，未重写 git 历史

**残留（已登记，非本轮范围）**：
- 1 条第三方弃用警告：`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`（Starlette 建议装 `httpx2`）。本轮未动 extras（`tests/test_extras_gate.py` 静态锁 extras 表）
- `ubuntu-latest` 的 Ubuntu 26 迁移 notice：2026-10-19 起该 runner 标签开始迁 Ubuntu 26；本轮通过时仍是 24.04。**下次 CI 变红先查这条**
- 诊断报告称负控红 11 个 seed，执行方实测 9 个（测量路径不同，见 §2 门禁 b′）

## 10. 复验方最该独立重做的五件事

1. **冻结集**：`sha256sum` 14 个文件与 §2 表中值逐条比；**再**用 manifest 登记的 13 条比一次（两个判据，别只做一个）
2. **跨 seed**：自己跑 15 个 seed；**并且**做一次负控（把 `"V6"` 塞回 `beverage-tea`），确认新守门会红
3. **干净环境**：从 GitHub clone + 全新 venv（别用本机已有 venv），跑 `pytest -q` 与五条命令；确认 `update/` 不在仓里
4. **发布件**：从 Release **真下载**三个附件，`sha256sum -c SHA256SUMS`，再装 wheel 跑业务命令
5. **CI**：给 §6 列出的 6 个 job 各查一次 annotations，确认 **Node20 弃用 0 条**；核对 job 名里的 Python 版本是 `3.12`、腿数是 2（不是 4）。三个 run 是 push main（代码）、push tag、push main（收尾回写），**都要看**。