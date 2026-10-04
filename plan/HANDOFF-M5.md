# HANDOFF-M5 —— 跨会话交接快照（M4 收尾，2026-10-04）【已过时仅作历史：M5 已完成（v0.6.0），续接读 HANDOFF-M6】

> 用法：新对话直接 `/goal 读取 "plan/HANDOFF-M5.md" 继续完成任务`。本快照先落盘再结束对话；M5 收尾后本文件头部标注"已过时仅作历史"，另写 HANDOFF-M6。

## 1. 当前进度（M0 ✅ + M1 ✅ + M2 ✅ + M3 ✅ + M4 ✅）

- plan/00–06 齐全且已回写（06 含 D01–D22；04/05 有 M4 变更记录）
- 包 `food_label_checker` v0.5.0，CLI `flcheck`；pytest **159 项全绿**（1–4s 全离线）
- **M4 交付**（基准与 LLM 兜底）：
  - **内置基准评测器迁入 src**（`src/food_label_checker/bench/`）：`bench/parse_eval.py`（字段级 P/R/F1，期望值只由 generate_dataset_with_states 内存重建，输入一律读冻结 fixtures 文件，D18）+ `bench/e2e_eval.py`（对账口径与 tests/test_engine_m3.py 等价迁入：覆盖集=main_expect∪also_expect(present_in)−also_expect(absent_in)，absent_in 字面对账，clean_baseline 零不合规，待人工不参与，dual_diff 仅 V5 产生 new_fails=[CLAIM-ZEROADD-01]）
  - **CLI `flcheck bench parse` / `bench e2e`**：退出码 0=达标 / 1=评测跑通但未达门槛 / 2=用法输入错误（D22 扩展约定）；门槛：parse F1≥0.95（`--min-f1` 可调）、e2e 误报 0+检出率 1.0+dual_diff 零违例
  - **实测指标（冻结集 seed-2026-n12，DATAGEN_VERSION=2）**：parse **F1=1.0**（TP=253/FP=0/FN=0）；e2e **检出率 1.0（9/9）、误报 0**（17 个 fail 实例全部被真值覆盖）、manual 0；已写进 README 评测表 + 一键复现 `flcheck bench parse && flcheck bench e2e`
  - **LLM 兜底适配器 `llm/`**（默认关闭）：`config.py`（FOOD_LABEL_LLM_* 环境变量/.env，env 优先；ENABLED/BASE_URL/API_KEY/MODEL/TIMEOUT_SECONDS/MAX_RETRIES）、`client.py`（OpenAI 兼容 chat/completions，enable_thinking=false，重试+超时，一切失败抛 LLMUnavailable）、`fallback.py`（候选行压缩：去空行/限 80 行/限 4000 字；防幻觉三闸：quote 必须 ⊆ 原文逐字子串、字段值从校验通过的 quote 用解析器同款正则重解析、confidence=0.7+region="LLM 兜底"+card.llm_assisted=True）；`pipeline.check_text(text, ids, llm_config=None)` 可选接入，输出恒含 `fallback` 报告（off/not_needed/applied/degraded）；CLI `check --llm` 显式开启；**全部测试 mock（httpx.MockTransport/stub），零真实 API**
  - **降级语义**：LLM 不可达/超时/配置缺失 → status="degraded"；unresolved 字段由规则层按 `unresolved_detail[param]=="present_unparsed"` 转"待人工确认"（行在值不可析——可能是解析覆盖不足而非标签违规），行整体缺失仍判不合规（V1 语义/e2e 契约不变）
  - **M3 推迟项联动落地（D22）**：2025 规则集 26 条（共 47 条 ≥40 DoD）——新增 NUTR-ROWS-01（强制营养行完整性 1+6，GB 28050-2025 §4.1，表整体缺失时 not_run 由 NUTR-TABLE-01 覆盖）与 ALLERGEN-01（致敏物质提示，GB 7718-2025 §4.12.1，关键词仅检索配料表）；check_type 9→11 种；均挂条文块 quote_ref、status=已核对；2011 豁免契约延续（新规则不入 2011）
  - **DATAGEN_VERSION 1→2**：模板补糖行（灭菌乳/食醋 0g；糖行无 NRV 不参与 V2/V3/V4 选取，RNG 流不变）+ 全模板致敏物质提示行；冻结集重生成 `data/generated/frozen/seed-2026-n12/`，位级复现守门（tests/test_datagen_repro.py）随动全绿；解析器增补 allergen_notice 字段（value=True/缺位，D19 同款）与 unresolved_detail
- 演示实测：`flcheck check examples/sample_label.txt --ruleset both` → 2011 stats {checked:15, fail:2}，2025 {checked:19, fail:4}，dual_diff.new_fails=[MAND-EXPIRY-01, SALT-NOTICE-01]（示例标签已补致敏物质提示行，ALLERGEN-01 通过）

## 2. M5 待办（编排与交付，DoD 详见 plan/05 §2 M5）

1. **pipeline 状态机**：节点 load_input → parse → llm 兜底（可选）→ run_ruleset×2 → merge+diff → emit；每节点记录耗时与状态；输入类失败明确报错退出，规则类失败降级为该 ruleset 结果缺失+警告不吞异常（plan/04 §5）
2. **docx 报告**（`report/`，python-docx，`.[report]` extra）：结论摘要 → 问题清单（分级）→ 证据表 → 整改建议 → 审查员签署栏 → 免责声明；"待人工确认"独立成节；**rels 无 External 外链**（0 外链纪律）+ LLM 参与标注（card.llm_assisted）
3. **Web 面板**（`webapp/`，FastAPI，`.[web]` extra）：单文件内联 HTML（vanilla JS）；路由 GET /、POST /api/check（multipart 上传文本→完整 JSON）、GET /api/health；0 外链断网可开，`docs_url=None, redoc_url=None`（冒烟测试已在 tests/test_webapp.py）
4. **CLI 收口**：`check --format table`、`--report out.docx`；extras 守门测试（pyproject extras 覆盖运行期+测试期 import，缺依赖时优雅降级）
5. **Web 真实上传冒烟**（urllib multipart+UTF-8 JSON，起真实 uvicorn 端口回环请求）
6. 既定口径清单固化进 HANDOFF-M6

## 3. 既定口径清单（动了会打挂基准/测试，先对照再动手）

- **真值语义/语料格式/V→规则契约（D16，v2）**：权威口径在 `src/food_label_checker/datagen/__init__.py` 模块注释——主期望+also_expect、评测按"全部非 pass 集合"对账、clean_baseline=双标尺零不合规、误报=未被真值覆盖的 fail；v2 语料格式新增：致敏物质提示行 `致敏物质提示：…`（全模板在位，解析为 allergen_notice 字段 value=True/缺位）+ 全模板 7 项营养行（灭菌乳/食醋糖行 0g）
- **V 主期望 rule_id（D16 契约，已全部入库）**：MAND-NAME/ING/NET/SHELF/DATE/STORAGE/SC-01、NRV-RECALC-01、ENERGY-CONSIST-01、CLAIM-THRESH-01、CLAIM-ZEROADD-01（仅 2025）、ING-ORDER-01、FMT-DATE-01、DATE-LOGIC-01、CLAIM-FUNC-01；另有 MAND-EXPIRY-01/SALT-NOTICE-01（2025）、FMT-DATE-02/ING-ORDER-02/NUTR-TABLE-01/MAND-STD-01/MAND-PRODUCER-01/MAND-ADDRESS-01/MAND-CONTACT-01、NUTR-ROWS-01/ALLERGEN-01（M4，仅 2025）
- **解析层字段契约（D19+D22）**：全部 P0 键在 card.fields；card.ingredients/claims 为镜像列表；nutrition_table 顶层列表（行 dict 含 name/amount/unit/nrv_percent/per_serving/evidence）；日期字段 value=ISO、原样标示在 evidence.quote；单位已归一；salt_oil_sugar_notice / allergen_notice value=True/缺位；**unresolved_detail**（key→"present_unparsed"）= 行在值不可析的机器可读标记；**llm_assisted**=LLM 兜底参与标注
- **引擎口径（M3/M4）**：11 种 check_type（+nutrition_rows/allergen_notice）；处理器返回列表、None=not_run；stats 三恒等式；门控 only_if 对全类型生效；conditional 三分支；NRV% 容差 ±1；能量低报方向 >120%+1kJ；claims 空时阈值/白名单规则产 pass 结论；present_unparsed 强制/条件规则→待人工确认；致敏关键词仅检索配料表
- **评测对账口径（D16/D21/D22）**：评测器在 `src/food_label_checker/bench/`；覆盖集=main_expect∪present_in−absent_in；检出率=检出的主期望/主期望总数；误报=未覆盖 fail（含 absent_in 违例、clean_baseline 违例）；合格线=误报 0+检出率 1.0+dual_diff 零违例；期望值只由 generate_dataset_with_states 内存重建，禁止语料反提；解析输入一律读冻结文件（D18）
- **CLI 退出码**：0=审查/评测完成且达标，1=bench 跑通但未达门槛，2=用法/输入错误；0 外链；测试全离线，LLM 一律 mock
- **指标门槛**：解析 F1≥0.95（实测 1.0）、误报 0（实测 0）——README 评测表已固化实测值，动引擎/解析器前先跑 bench
- **2011 豁免契约**：2011 规则集不得含 CLAIM-ZEROADD-01/NUTR-ROWS-01/ALLERGEN-01，不得对盐油糖提示语/致敏物质提示/2025 新增强制项报不合规
- **知识层契约（D20）**：L1 raw/ PDF（sha256 台账）→ L2 blocks/ 条文块（428 块）→ L3 rulesets/*.json（basis.quote_ref 挂 L2）；"无出处不落库"由 tests/test_blocks.py + test_rulesets_schema.py 守门；新规则必须先有块再有规则（47 条全部已核对）
- **确定性近似口径（D20/D22）**：日期格式按 `YYYY年MM月DD日` 从严判定；配料递减序=品类先验对；豁免=关键词近似；到期日推算共用 datagen.templates；致敏物质=D.2.2 引导词字面子集+八类关键词仅查配料表
- **LLM 兜底契约（D22）**：默认关闭；数值结论永远来自确定性规则（FR-13）；quote ⊆ 原文逐字子串硬校验；值从 quote 重解析；confidence=0.7；降级不吞结论不造结论
- **数值唯一出处**：rules/nutrient_reference.json（含机器可读 claim_thresholds）；flagged_pending_basis 引擎自动置位
- **复现纪律（D16/D18/D22）**：模板/生成器/冻结集任一侧变更 → 重生成冻结集并升 DATAGEN_VERSION（守门测试强制暴露）

## 4. 本机环境坑（仅记实测）

- 本机 Python 3.8.8（`py` 启动器；`python` 是商店占位符），跑脚本带 `PYTHONDONTWRITEBYTECODE=1`；**3.8 无 `Path.write_text(newline=)`**（写文件用 open(..., newline="\n")）
- **Git Bash heredoc 传中文给 py stdin 会编码报错**（Non-UTF-8 code...）——中文补丁脚本先 Write 落盘 .py 文件再 `py -X utf8 file.py` 执行，跑完即删
- `flcheck.exe` 装在 `...\Python38\Scripts\`（不在 PATH）——用 `py -m food_label_checker` 或 `py -X utf8` 等价；GBK 控制台已做 errors=replace 兜底
- pip 曾被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`
- 本机可用 PyMuPDF（fitz）/pypdf——非运行期依赖，仅 tools/build_blocks.py 数据准备用；核心通路保持纯 stdlib（D07）
- **fastapi 导入偶发随机 SystemError（bad argument to internal function）导致 pytest collection 中断**——本机不稳定抖动，重跑即可；pytest 输出先落盘再解析（`> file 2>&1`）
- gh 已登录 `yuluo554`，token scopes 无 `workflow` → **建仓推送必须走 SSH**（D12）
- Git Bash `/tmp` 与 Windows Python 路径不通；临时文件用工作区相对路径
- 长命令偶发被中断（本机稳定性），重跑即可；关键命令输出先落盘再解析

## 5. M4 DoD 对照（逐项）

- [x] LLM 适配器（OpenAI 兼容、enable_thinking=false、候选行压缩、逐字摘录子串校验、不可达降级，全测试 mock）：`llm/` 三件套 + pipeline/CLI 集成，25 项 mock 测试零真实 API
- [x] bench parse（F1≥0.95）可重复跑通：评测器迁入 src/food_label_checker/bench/，实测 F1=1.0（TP=253/FP=0/FN=0），退出码门槛固化
- [x] bench e2e（误报 0，检出率达标）：对账语义与 test_engine_m3.py 等价迁入，实测检出率 1.0（9/9）、误报 0、dual_diff 零违例
- [x] 指标写进 README 评测表：实测值 + `flcheck bench parse && flcheck bench e2e` 一键复现
- [x] 既定口径清单固化进 HANDOFF：本文件 §3
- [x] M3 推迟项联动（可选建议项，已做）：NUTR-ROWS-01/ALLERGEN-01 入库挂条文块；模板 v2（糖行+致敏原行）+ 冻结集重生成 DATAGEN_VERSION=2；守门测试全绿

## 6. 关键命令速查

```bash
# 安装与测试（仓库根目录）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q

# M4 演示物（bench 一键复现；退出码 0=达标）
py -X utf8 -m food_label_checker bench parse
py -X utf8 -m food_label_checker bench e2e
py -X utf8 -m food_label_checker bench parse && py -X utf8 -m food_label_checker bench e2e

# 双标尺演示（LLM 兜底默认关；--llm 需 FOOD_LABEL_LLM_* 配置）
py -X utf8 -m food_label_checker check examples/sample_label.txt --ruleset both
py -X utf8 -m food_label_checker check data/generated/frozen/seed-2026-n12/sample-0009-dairy-fermented.txt --ruleset both  # V5：仅 2025 报 CLAIM-ZEROADD-01

# 生成器（冻结集重生成必须升 DATAGEN_VERSION 并跑守门测试；当前 v2）
py -X utf8 -m food_label_checker gen --seed 2026 --n 12 --out data/generated/frozen --force

# 条文块重建（仅 PDF 更换时需要；提取文本随仓在 raw/_extracted/）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/build_blocks.py

# git（本仓库身份已配好，勿改 user.email）
git log --format="%h %ae %ce" --all   # 应只见 282769740+yuluo554@users.noreply.github.com
```
