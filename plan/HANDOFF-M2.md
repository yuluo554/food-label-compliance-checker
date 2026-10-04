# HANDOFF-M2 —— 跨会话交接快照（M1 收尾，2026-10-04）

> **【已过时，仅作历史】** M2 已于 2026-10-04 完成并提交，当前有效快照为 [HANDOFF-M3.md](HANDOFF-M3.md)。本文档保留 M1 收尾时的口径清单与环境坑（已并入 HANDOFF-M3），M2 待办勿再按此执行。

> 用法：新对话直接 `/goal 读取 "plan/HANDOFF-M2.md" 继续完成任务`。本快照先落盘再结束对话；M2 收尾后本文件头部标注"已过时仅作历史"，另写 HANDOFF-M3。

## 1. 当前进度（M0 ✅ + M1 ✅）

- plan/00–06 齐全且已回写（06 含 D01–D18；04 有 M1 变更记录）
- 骨架可装可跑：`pip install -e .`，包 `food_label_checker`，CLI `flcheck`（v0.2.0）
- **M1 交付**：datagen 生成器（4 品类 8 小类模板 + V1–V8 注入器 + 真值 JSON）；`flcheck gen --seed --n --categories --out --force` 落地；冻结 fixtures `data/generated/frozen/seed-2026-n12/`（4 干净 + V1–V8 各 1）入仓；守门测试 pytest **38 项全绿**（0.8s 全离线）：datagen 复现/schema 11 项 + EOL 守门 3 项 + M0 既有 24 项
- **标准原文入库**：四部官方 PDF（GB 7718/28050 新旧版）经食品安全国家标准数据检索平台直下入库 `data/knowledge/raw/`（渠道/GUID/sha256 见 raw/retrieval-log.md；卫健委 WAF 需真实浏览器，检索平台表单 POST 可 curl）
- **数值核验升级**：NRV 基准值/能量系数(17/37/17)/无糖阈值(≤0.5g/100g(mL))/作用声称白名单/允许误差表2（实际≤120%标示值）逐项挂原文核对 → `src/food_label_checker/rules/nutrient_reference.json` status=已核对（随包分发，package-data 已配）
- CI/README/LICENSE/.gitattributes/data 台账（data/README.md）就绪；git 身份 noreply（D11）不变

## 2. M2 待办（解析层，DoD 详见 plan/05 §2）

1. 文本标签解析器覆盖参数卡字段表全部 P0 字段（plan/04 §1.1）：食品名称/配料/净含量/生产日期/保质期/保质期到期日/贮存条件/生产者三项/SC 号/产品标准代号/营养表（制表符三列，含饱和脂肪行+盐油糖提示语行）/声称（`声称：` 前缀行）
2. 证据（区域+逐字摘录+span）挂全——quote 必须是输入子串（现有测试锁定）；V7a 非规范日期须解析出日期值（格式问题归 FMT-DATE-01，不得误报缺生产日期，契约见 datagen/__init__.py §6）
3. 每解析器配生成器样例回归测试（用 data/generated/frozen/ 冻结集，勿重生成）
4. 解析 F1 自测（冻结集子集）≥0.9（M4 全量口径定稿）；`flcheck parse <file>` 输出参数卡 JSON

## 3. 既定口径清单（动了会打挂基准/测试，先对照再动手）

- **真值语义/语料格式/V→规则契约（D16）**：权威口径在 `src/food_label_checker/datagen/__init__.py` 模块注释——主期望+also_expect、评测按"全部非 pass 集合"对账、clean_baseline=双标尺零不合规、误报=未被真值覆盖的 fail；V 主期望 rule_id（MAND-NAME/ING/NET/SHELF/DATE/STORAGE/SC-01、NRV-RECALC-01、ENERGY-CONSIST-01、CLAIM-THRESH-01、CLAIM-ZEROADD-01（仅 2025，2011 不得报）、ING-ORDER-01、FMT-DATE-01、DATE-LOGIC-01、CLAIM-FUNC-01）是 M3 规则库硬约束
- **指标门槛**：解析 F1≥0.95、误报 0（不放宽）
- **无出处不落库**：basis.status 两值（已核对/待核对）；`flagged_pending_basis` 引擎自动置位； nutrient_reference.json 已核对条目可输出确定语气（附出处），其余仍按待核对纪律
- **M3 契约要点（原文核验结论）**：2025 强制标示 7 项（能量/蛋白/脂肪/饱和脂肪/碳水/糖/钠）+ 盐油糖提示语（§4.1/§4.5）；**2011 规则集不得对"儿童青少年应避免过量摄入盐油糖。"提示语或自愿性营养行（饱和脂肪/糖）报不合规**；能量容差按表2（实际 ≤120% 标示值，两版一致）；V3 注入为纯低报方向（shown=0.5–0.75×correct）
- **门控纪律**：`only_if` 对全部 check_type 生效（test_engine_dual 锁定）
- **规则集枚举**：`AVAILABLE_RULESETS` 与 rulesets/*.json 一一对应（test_rulesets_dir_matches_available 锁定）；新增规则集必须同步该元组
- **结论三级**：合规/不合规/待人工确认；未知 check_type 转"待人工确认"不崩溃
- **CLI 退出码**：0=审查完成（含检出不合规），2=用法/输入错误
- **0 外链**：webapp docs_url/redoc_url 必须 None（测试锁定）
- **测试全离线**：LLM 一律 mock；核心通路 import 不触达 extras 包
- **复现纪律（D16/D18）**：模板/生成器/冻结集任一侧变更 → 重生成冻结集并升 DATAGEN_VERSION（守门测试强制暴露）；M3 扩规则库若新增对干净样本适用的规则，同步模板与冻结集

## 4. 本机环境坑（仅记实测）

- 本机 Python 3.8.8（`py` 启动器；`python` 是商店占位符），跑脚本带 `PYTHONDONTWRITEBYTECODE=1`；3.8 无 `Path.write_text(newline=)`（datagen 已用 open() 绕开，新代码注意）
- `flcheck.exe` 装在 `...\Python38\Scripts\`（不在 PATH）——用 `py -m food_label_checker` 或 `py -X utf8` 等价；GBK 控制台已做 errors=replace 兜底
- pip 曾被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`
- gh 已登录 `yuluo554`，token scopes 无 `workflow` → **建仓推送必须走 SSH**（D12）
- Git Bash `/tmp` 与 Windows Python 路径不通；临时文件用工作区相对路径
- 卫健委官网主站有瑞数 WAF（curl/WebFetch 412）：需真实浏览器（ZCode 内置浏览器已验证可过）；检索平台 sppt.cfsa.net.cn:8086 是 HTTPS，附件走表单 POST（raw/retrieval-log.md 有可直接复用的 curl 命令参数）

## 5. M1 DoD 对照（逐项）

- [x] datagen 8 类注入器 + 真值 JSON（固定 seed 位级复现，manifest sha256 守门）
- [x] ≥4 品类模板各 ≥ 干净版 1 + 注入版若干（4 品类 8 小类；冻结集 12 样本覆盖 V1–V8 全部类型，测试锁定）
- [x] `data/knowledge/raw/` 至少入库 1 部标准原文（实际四部全入库，挂渠道+sha256 台账）
- [x] NRV/能量系数表建"待核对"条目（超额：已挂原文逐项核对升"已核对"，D17）
- [x] 数据台账登记齐全（data/README.md + raw/retrieval-log.md + plan/00/04/05/06 回写）
- [x] fixtures 冻结策略 + EOL 守门测试落位（D18；test_datagen_repro.py + test_eol_guard.py）
- [x] 演示物 `flcheck gen --seed 42` 出带真值数据集（实测通过）

## 6. 关键命令速查

```bash
# 安装与测试（仓库根目录）
PYTHONDONTWRITEBYTECODE=1 py -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 py -m pytest -q

# 生成器
py -X utf8 -m food_label_checker gen --seed 42                 # 默认 n=12 → data/generated/seed-42-n12/
py -X utf8 -m food_label_checker gen --seed 2026 --n 12 --out data/generated/frozen --force  # 重生成冻结集（改生成器后必须做，升 DATAGEN_VERSION）

# 骨架演示
py -X utf8 -m food_label_checker --version
py -X utf8 -m food_label_checker check examples/sample_label.txt --ruleset both
py -X utf8 -m food_label_checker parse examples/sample_label.txt

# git（本仓库身份已配好，勿改 user.email）
git log --format="%h %ae %ce" --all   # 应只见 282769740+yuluo554@users.noreply.github.com
```
