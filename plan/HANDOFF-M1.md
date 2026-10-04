# HANDOFF-M1 —— 跨会话交接快照（M0 收尾，2026-10-04）

> 用法：新对话直接 `/goal 读取 "plan/HANDOFF-M1.md" 继续完成任务`。本快照先落盘再结束对话；M1 收尾后本文件头部标注"已过时仅作历史"，另写 HANDOFF-M2。

## 1. 当前进度（M0 已完成 ✅）

- plan/00–06 齐全（00 总览、01 题目、02 需求、03 架构、04 详设、05 里程碑、06 决策 D01–D15）
- 骨架可安装可运行：`pip install -e .`，包 `food_label_checker`，CLI `flcheck`（v0.1.0）
- **垂直切片通电**：`flcheck check examples/sample_label.txt --ruleset both` 真实跑通双标尺 JSON 审查（2011: 3 查 1 不合规；2025: 4 查 2 不合规；`dual_diff.new_fails=["MAND-EXPIRY-01"]`）
- 测试 25 项全绿（0.5s，全离线）：models/parser/engine 双标尺/门控/未知类型转待人工/规则集 schema 守门/CLI 成败路径/webapp 冒烟（importorskip）
- CI（{ubuntu,windows}×{3.8,3.11}，装 `.[dev,web,report]`）、README、LICENSE(MIT)、.gitattributes(`* text=auto eol=lf`)、data 台账就绪
- git 身份已切 GitHub noreply（D11），根提交已重写为 `f0a179f`

## 2. M1 待办（数据先行，DoD 详见 plan/05 §2）

1. datagen 生成器：4 品类模板（乳制品/饮料/烘焙/调味品）+ V1–V8 注入器 + 真值 JSON（主期望+also_expect 语义，写进生成器模块注释）；`flcheck gen --seed` 落地
2. 固定 seed 位级复现守门测试（--force 重生成 git status 零变化）
3. 标准原文入库启动：GB 7718-2011/2025、GB 28050-2011/2025 → `data/knowledge/raw/`（渠道见 plan/05 §1.2，WebSearch 摘要不采信数值，官方页面直连核验）
4. NRV 基准值/能量系数表建"待核对"条目（挂原文前不得确定语气）
5. fixtures 冻结策略落位（入仓小集 + CR 守门测试，.gitattributes 已前置）
6. 数据台账逐项登记（data/README.md），plan/00、05、06 回写

## 3. 既定口径清单（动了会打挂基准/测试，先对照再动手）

- **真值语义**：注入项记主期望，同一注入隐含结论记 also_expect；评测按"文档全部非 pass 集合"对账（M1 生成器注释里定稿后不得单方更改）
- **指标门槛**：解析 F1≥0.95、误报 0（不放宽）
- **无出处不落库**：basis.status 只有两值（已核对/待核对）；`flagged_pending_basis` 由引擎按 status 自动置位；tests/test_rulesets_schema.py 是守门
- **门控纪律**：`only_if` 对全部 check_type 生效（tests/test_engine_dual.py::test_only_if_gate_blocks_other_category 锁定）
- **规则集枚举**：`AVAILABLE_RULESETS` 与 rulesets/*.json 文件一一对应（test_rulesets_dir_matches_available 锁定）；新增规则集必须同步该元组
- **结论三级**：合规/不合规/待人工确认；未知 check_type 转"待人工确认"不崩溃（有测试锁定）
- **CLI 退出码**：0=审查完成（含检出不合规），2=用法/输入错误
- **0 外链**：webapp docs_url/redoc_url 必须 None（有测试锁定）
- **测试全离线**：LLM 一律 mock；核心通路（parser/rules/pipeline/cli）import 不触达 extras 包

## 4. 本机环境坑（仅记实测）

- 本机 Python 3.8.8（`py` 启动器；`python` 是商店占位符），跑脚本带 `PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏前科预防）
- `flcheck.exe` 装在 `...\Python38\Scripts\`（不在 PATH）——用 `py -m food_label_checker` 或 `py -X utf8` 等价；控制台 GBK 时 CLI 输出已做 errors=replace 兜底
- pip 曾被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`
- gh 已登录 `yuluo554`，token scopes 无 `workflow` → **建仓推送必须走 SSH**（D12），https+token 推含 workflows 的仓库会被拒
- Git Bash `/tmp` 与 Windows Python 路径不通；临时文件用工作区相对路径

## 5. M0 DoD 对照（逐项）

- [x] plan/00–06 齐全且状态回写
- [x] `pip install -e .` 可装（实测成功）
- [x] CLI `--version/--help` 可用
- [x] 垂直切片：`flcheck check examples/sample_label.txt --ruleset both` 双标尺 JSON 真实输出
- [x] pytest 全绿（25 passed；含失败路径：缺文件/坏编码/未知规则集/未实现子命令）
- [x] CI 配置就绪（.github/workflows/ci.yml；首跑验证在 M6 建仓后）
- [x] README/LICENSE/.gitattributes/data 台账就绪
- [x] git 身份切 noreply + 根提交重写（D11）

## 6. 关键命令速查

```bash
# 安装与测试（仓库根目录）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q

# 骨架演示
py -X utf8 -m food_label_checker --version
py -X utf8 -m food_label_checker check examples/sample_label.txt --ruleset both
py -X utf8 -m food_label_checker parse examples/sample_label.txt

# git（本仓库身份已配好，勿改 user.email）
git log --format="%h %ae %ce" --all   # 应只见 282769740+yuluo554@users.noreply.github.com
```
