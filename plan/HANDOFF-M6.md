# HANDOFF-M6 —— 跨会话交接快照（M5 收尾，2026-10-04）【已过时仅作历史：M6 已收尾并发布，终态见 HANDOFF-FINAL.md】

> 用法：新对话直接 `/goal 读取 "plan/HANDOFF-M6.md" 继续完成任务`。本快照先落盘再结束对话；M6 收尾后本文件头部标注"已过时仅作历史"，另写 HANDOFF-FINAL（发布收尾快照）。（2026-10-04 注：M6 已收尾，本快照仅作历史，发布实录见 plan/RELEASE-M6.md。）

## 1. 当前进度（M0 ✅ + M1 ✅ + M2 ✅ + M3 ✅ + M4 ✅ + M5 ✅）

- plan/00–06 齐全且已回写（06 含 D01–D23；00/05 有 M5 变更记录）
- 包 `food_label_checker` v0.6.0，CLI `flcheck`；pytest **189 项全绿**（1–4s 全离线，分 5 批各 ≤70）
- **M5 交付**（编排与交付，D23）：
  - **pipeline 状态机**（`pipeline.run_pipeline`）：节点 load_input → parse → llm_fallback（可选）→ run_ruleset×N → merge_diff → emit；每节点 {node, status(ok/skipped/degraded), elapsed_ms, detail} 随结果 JSON `pipeline.nodes` 返回，降级节点汇入 `warnings`；输入类失败（缺文件/坏编码）异常明确报错退出（CLI 退出码 2），规则类失败降级为该 ruleset 结果缺失+警告（异常详情入 trace 不吞异常），一侧缺失时 dual_diff 跳过；`check_text` M4 结果键契约不变（新测试 test_pipeline_trace.py 锁定）
  - **docx 报告**（`report/docx_report.py`，`.[report]` extra）：七节结构——结论摘要（含双标尺统计表+流程节点表）→ 问题清单（分级）→ **待人工确认独立成节** → 证据表 → 整改建议 → 审查员签署栏 → 免责声明；LLM 参与标注（card.llm_assisted）写元信息+免责声明；rels 零 External（test_report.py 硬断言全部 rels 包件）；CLI `check --report out.docx`（提示走 stderr，stdout 保持 JSON）；样例报告不入仓，命令即时生成
  - **Web 面板**（`webapp/`，`.[web]` extra）：`page.py` 零依赖内联单页（vanilla JS+inline CSS，无构建/无 vendor）；`GET /`（整页无 http(s) 引用，含无 SVG xmlns）、`POST /api/check`（multipart file 字段或 text 字段二选一 + ruleset + llm 表单字段 → 完整审查 JSON；缺输入/未知规则集/坏编码 → 400）、`GET /api/health`；`docs_url=None, redoc_url=None`；**webapp 模块禁用 `from __future__ import annotations`**（pydantic 回解不到 create_app 内导入的 UploadFile，PydanticUserError）
  - **CLI 收口**：`check --format table`（人读摘要：统计行+分级结论+依据+建议+证据+dual_diff 摘要）、`--report out.docx`、`flcheck web --host/--port`（uvicorn 缺失时退出码 2+安装提示）
  - **extras 守门**（tests/test_extras_gate.py）：静态解析 pyproject 断言 web={fastapi,uvicorn,python-multipart}、report={python-docx}、dev={pytest,httpx} 且 src/tests 全部可选 import 被某 extra 声明（python-multipart 缺失时 uvicorn 启动即崩、TestClient 需 httpx——第三形态对冲）；缺依赖 mock 注入测试：惰性导入抛带安装提示 ImportError、CLI 优雅降级退出码 2
  - **Web 真实上传冒烟**（tests/test_webapp_smoke.py）：真实 uvicorn 回环端口（线程起服）+ urllib `ProxyHandler({})` 直连（绕过注册表系统代理）发 multipart UTF-8 中文标签 → 完整 JSON 断言（health/index/multipart 三测）；CLI 层 `flcheck web` 真实起服探活实测通过
- **bench 复跑零回退（M5 收尾实测）**：parse F1=1.0（TP=253/FP=0/FN=0）、e2e 检出率 1.0（9/9）、误报 0、dual_diff 零违例
- 演示实测：`flcheck check examples/sample_label.txt --format table`（2011 {15, fail 2}，2025 {19, fail 4}，dual_diff 新增 [MAND-EXPIRY-01, SALT-NOTICE-01]）；`check --report` 生成 39KB docx（3 rels 包件 0 External，演示后即删）

## 2. M6 待办（脱敏发布 + 收尾固化，DoD 详见 plan/05 §2 M6）

1. **脱敏四步复核 + 提交元数据邮箱检查**（D11 已前置完成 noreply 切换与根提交重写，复核即可）：`git ls-files` 敏感文件扫描（应为空）→ 全部跟踪文本内容级扫描（sk- 密钥/手机号/身份证/个人路径/内网 IP/邮箱）→ 二进制样例单独扫（本仓无 docx/xlsx 样例入仓，核对台账）→ 已推送则重写历史（本仓**尚未建远端**，首推前完成即可，无需 force push）——逐项留档 `plan/RELEASE-M6.md`；扫描模式文本注意占位化（阶段 7 实录：模式字面值本身会永留历史）
2. **历史终验三扫全 0**（内容 grep / log -p / 提交信息），先跑阳性对照验证扫描命令本身；MSYS `/` 起始参数静默转写坑见 §4
3. **干净环境验证（发布门核心）**：新目录 `git clone`（本地 clone 即可，发布后 GitHub clone 复核再补）+ 全新 `py -m venv`，**按 README 原文逐字**执行快速开始（注意 README 已内置 `pip install -U pip` 前置行——3.8 自带老 pip 装不了 pyproject-only 项目）+ 全链 demo（check/parse/gen/bench/table/report/web）；**pytest 收集数对照**：干净环境装 `.[dev,web,report]` 后收集数必须与 dev 一致（189）——不一致=extras 静默缺依赖（importorskip 第三形态），暴露的问题修复后必加回归测试
4. **gh 建仓走 SSH**（D12，token 无 workflow scope）：`gh repo create yuluo554/food-label-compliance-checker --public --description "..." --source . --remote origin`（**不带 --push**）→ `ssh -T git@github.com` 验证 → `git remote set-url origin git@github.com:yuluo554/food-label-compliance-checker.git` → push 一次成；git 链执行前 `pwd` + `git log --oneline -1` + `git remote -v` 三核对
5. **tag+release（对外动作，先向用户确认一次打包授权）**：`git tag -a v0.6.0` + push tag + `gh release create v0.6.0 --notes-file <md>`（notes=评测表数值+演示命令摘要+extras 说明）；tag 打在含收尾回写文档的提交上
6. **topics**：`gh repo edit --add-topic`（小写连字符，如 food-label / gb7718 / gb28050 / food-safety / compliance / rules-engine），加完 `gh api` 回读确认
7. **发布后复核**：GitHub 全新 clone → 全量测试 + bench + 历史三扫；`gh run list` 对账 CI 轮数与 push 数一致
8. **收尾回写**：plan/00/05/06 回写 ✅（含 D15 赛事缓议项一并定夺或顺延）、RELEASE-M6.md 落盘、HANDOFF-FINAL 或直接收尾小提交
9. D15（是否投真实赛事）M5 后窗口期另查再议——M6 收尾时向用户确认处置

## 3. 既定口径清单（动了会打挂基准/测试，先对照再动手）

- **真值语义/语料格式/V→规则契约（D16，v2）**：权威口径在 `src/food_label_checker/datagen/__init__.py` 模块注释——主期望+also_expect、评测按"全部非 pass 集合"对账、clean_baseline=双标尺零不合规、误报=未被真值覆盖的 fail；v2 语料：致敏物质提示行 `致敏物质提示：…`（解析为 allergen_notice value=True/缺位）+ 全模板 7 项营养行（灭菌乳/食醋糖行 0g）
- **V 主期望 rule_id（D16 契约）**：MAND-NAME/ING/NET/SHELF/DATE/STORAGE/SC-01、NRV-RECALC-01、ENERGY-CONSIST-01、CLAIM-THRESH-01、CLAIM-ZEROADD-01（仅 2025）、ING-ORDER-01、FMT-DATE-01、DATE-LOGIC-01、CLAIM-FUNC-01；另有 MAND-EXPIRY-01/SALT-NOTICE-01（2025）、FMT-DATE-02/ING-ORDER-02/NUTR-TABLE-01/MAND-STD-01/MAND-PRODUCER-01/MAND-ADDRESS-01/MAND-CONTACT-01、NUTR-ROWS-01/ALLERGEN-01（仅 2025）
- **解析层字段契约（D19+D22）**：全部 P0 键在 card.fields（净含量键名 **net_content**，value={amount,unit[,spec]}）；card.ingredients/claims 为镜像列表；nutrition_table 顶层列表（行 dict 含 name/amount/unit/nrv_percent/per_serving/evidence）；日期字段 value=ISO、原样标示在 evidence.quote；单位已归一；salt_oil_sugar_notice / allergen_notice value=True/缺位；unresolved_detail（key→"present_unparsed"）；llm_assisted
- **引擎口径（M3/M4）**：11 种 check_type（+nutrition_rows/allergen_notice）；处理器返回列表、None=not_run；stats 三恒等式；门控 only_if 对全类型生效；conditional 三分支；NRV% 容差 ±1；能量低报方向 >120%+1kJ；claims 空时阈值/白名单规则产 pass 结论；present_unparsed 强制/条件规则→待人工确认；致敏关键词仅检索配料表
- **评测对账口径（D16/D21/D22）**：评测器在 `src/food_label_checker/bench/`；覆盖集=main_expect∪present_in−absent_in；检出率=检出的主期望/主期望总数；误报=未覆盖 fail（含 absent_in 违例、clean_baseline 违例）；合格线=误报 0+检出率 1.0+dual_diff 零违例；期望值只由 generate_dataset_with_states 内存重建，禁止语料反提；解析输入一律读冻结文件（D18）
- **CLI 退出码**：0=审查/评测完成且达标，1=bench 跑通但未达门槛，2=用法/输入错误（**含可选扩展依赖缺失**——报错带 pip install 提示）；0 外链；测试全离线，LLM 一律 mock
- **pipeline trace 契约（D23，M5）**：结果 JSON 顶层键 engine_version/ruleset_ids/card/fallback/results/pipeline/warnings（双规则集时 +dual_diff）；节点序列 load_input→parse→llm_fallback→run_ruleset:{rid}→merge_diff→emit，status∈{ok,skipped,degraded}；规则类失败=该 rid 从 results 缺失+degraded 节点+warnings 记录+merge_diff 降级+dual_diff 跳过；`check_text` 契约不变（test_pipeline_trace.py 锁定）
- **报告/面板 0 外链纪律（D23，M5）**：docx 全部 rels 包件无 `TargetMode="External"`（test_report.py）；Web 页面整页无 `http://`/`https://` 子串（含无 SVG xmlns，test_webapp.py 对源码常量+路由双层断言）；`docs_url=None, redoc_url=None` 恒关闭；docx 样例报告不入仓（命令即时生成）
- **extras 契约（D23，M5）**：web={fastapi,uvicorn,python-multipart}（multipart 缺失 uvicorn 启动即崩）、report={python-docx}、dev={pytest,httpx}（TestClient 需 httpx）、llm={httpx}；test_extras_gate.py 静态守门 pyproject 声明 + src/tests 可选 import 全覆盖；**新可选 import 必须先入 extra**；webapp 模块禁用 future annotations（pydantic UploadFile 坑）
- **指标门槛**：解析 F1≥0.95（实测 1.0）、误报 0（实测 0）——README 评测表已固化实测值，动引擎/解析器前先跑 bench
- **2011 豁免契约**：2011 规则集不得含 CLAIM-ZEROADD-01/NUTR-ROWS-01/ALLERGEN-01，不得对盐油糖提示语/致敏物质提示/2025 新增强制项报不合规
- **知识层契约（D20）**：L1 raw/ PDF（sha256 台账）→ L2 blocks/ 条文块（428 块）→ L3 rulesets/*.json（basis.quote_ref 挂 L2）；"无出处不落库"由 tests/test_blocks.py + test_rulesets_schema.py 守门；新规则必须先有块再有规则（47 条全部已核对）
- **确定性近似口径（D20/D22）**：日期格式按 `YYYY年MM月DD日` 从严判定；配料递减序=品类先验对；豁免=关键词近似；到期日推算共用 datagen.templates；致敏物质=D.2.2 引导词字面子集+八类关键词仅查配料表
- **LLM 兜底契约（D22）**：默认关闭；数值结论永远来自确定性规则（FR-13）；quote ⊆ 原文逐字子串硬校验；值从 quote 重解析；confidence=0.7；降级不吞结论不造结论
- **数值唯一出处**：rules/nutrient_reference.json（含机器可读 claim_thresholds）；flagged_pending_basis 引擎自动置位
- **复现纪律（D16/D18/D22）**：模板/生成器/冻结集任一侧变更 → 重生成冻结集并升 DATAGEN_VERSION（守门测试强制暴露）

## 4. 本机环境坑（仅记实测）

- 本机 Python 3.8.8（`py` 启动器；`python` 是商店占位符），跑脚本带 `PYTHONDONTWRITEBYTECODE=1`；**3.8 无 `Path.write_text(newline=)`**（写文件用 open(..., newline="\n")）
- **Git Bash heredoc 传中文给 py stdin 会编码报错**——中文补丁脚本先 Write 落盘 .py 文件再 `py -X utf8 file.py` 执行，跑完即删
- `flcheck.exe` 装在 `...\Python38\Scripts\`（不在 PATH）——用 `py -m food_label_checker` 或 `py -X utf8` 等价；GBK 控制台已做 errors=replace 兜底（Bash 工具输出里的 UTF-8 乱码是显示问题，文件本体无损——Read 工具读不受影响）
- pip 曾被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`；**urllib/requests 回环请求也会走注册表系统代理**——Web 探活/冒烟必须 `urllib.request.build_opener(urllib.request.ProxyHandler({}))` 直连（test_webapp_smoke.py 已内置）
- 本机可用 PyMuPDF（fitz）/pypdf——非运行期依赖，仅 tools/build_blocks.py 数据准备用；核心通路保持纯 stdlib（D07）
- **fastapi 导入偶发随机 SystemError（bad argument to internal function）导致 pytest collection 中断**——本机不稳定抖动，重跑即可；pytest 输出先落盘再解析（`> file 2>&1`）
- **capsys.readouterr() 每次调用清空缓冲**——测试里要同时断言 out 和 err 时必须接一次返回值再用两字段（M5 实录）
- gh 已登录 `yuluo554`，token scopes 无 `workflow` → **建仓推送必须走 SSH**（D12）
- Git Bash `/tmp` 与 Windows Python 路径不通；临时文件用工作区相对路径；以 `/` 开头的 grep 参数会被 MSYS 静默转写（扫描模式用包含形式+阳性对照）
- 长命令偶发被中断（本机稳定性），重跑即可；关键命令输出先落盘再解析；测试多时分批跑（每批 ≤70，批间 sleep 2s）

## 5. M5 DoD 对照（逐项）

- [x] pipeline 状态机：节点耗时+状态（`pipeline.nodes`/`warnings`），输入类失败报错退出、规则类失败降级不吞异常——test_pipeline_trace.py 6 项锁定
- [x] docx 报告（七节结构、待人工独立成节、签署栏+免责声明、rels 无 External、LLM 标注）——test_report.py 6 项
- [x] Web 面板（内联单页 0 外链断网可开、docs/redoc 关闭、multipart 上传→完整 JSON）——test_webapp.py 9 项
- [x] CLI 收口（`check --format table`、`--report out.docx`、`flcheck web`）；extras 守门测试（覆盖运行期+测试期 import，缺依赖优雅降级退出码 2）——test_extras_gate.py 7 项 + test_cli.py 增补
- [x] Web 真实上传冒烟（真实 uvicorn 回环 + urllib multipart UTF-8 JSON）——test_webapp_smoke.py 3 项
- [x] 既定口径清单固化进 HANDOFF-M6：本文件 §3
- [x] bench 复跑零回退（F1=1.0/误报 0/检出率 1.0）；pytest 189 项全绿；版本 v0.6.0

## 6. 关键命令速查

```bash
# 安装与测试（仓库根目录；extras 全装保证 pytest 收集数=189）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e ".[dev,web,report]"
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q          # 全量分批：见 §4 分批纪律

# bench 一键复现（退出码 0=达标）
py -X utf8 -m food_label_checker bench parse
py -X utf8 -m food_label_checker bench e2e

# M5 演示物
py -X utf8 -m food_label_checker check examples/sample_label.txt --format table
py -X utf8 -m food_label_checker check examples/sample_label.txt --report data/generated/demo_report.docx   # 演示后即删
py -X utf8 -m food_label_checker web --port 8000   # 浏览器开 http://127.0.0.1:8000

# 双标尺 JSON（LLM 兜底默认关；--llm 需 FOOD_LABEL_LLM_* 配置）
py -X utf8 -m food_label_checker check examples/sample_label.txt --ruleset both
py -X utf8 -m food_label_checker check data/generated/frozen/seed-2026-n12/sample-0009-dairy-fermented.txt --ruleset both  # V5：仅 2025 报 CLAIM-ZEROADD-01

# 生成器（冻结集重生成必须升 DATAGEN_VERSION 并跑守门测试；当前 v2）
py -X utf8 -m food_label_checker gen --seed 2026 --n 12 --out data/generated/frozen --force

# 条文块重建（仅 PDF 更换时需要；提取文本随仓在 raw/_extracted/）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/build_blocks.py

# git（本仓库身份已配好，勿改 user.email；M6 建仓推送走 SSH，D12）
git log --format="%h %ae %ce" --all   # 应只见 282769740+yuluo554@users.noreply.github.com
```
