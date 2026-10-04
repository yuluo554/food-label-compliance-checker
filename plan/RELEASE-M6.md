# RELEASE-M6 —— 脱敏发布留档（2026-10-04）

> M6 发布门逐项实录。扫描工具：`tools/scan_sensitive.py`（本仓新增，可复跑）。
> 纪律：本文件与扫描器源码均不含敏感模式字面值/假样值（占位化，防"模式字面值永留历史"）。

## 1. 脱敏四步复核

| 步骤 | 方法 | 结果 |
|---|---|---|
| ① 敏感文件清单扫描 | `git ls-files`（106 个跟踪文件）逐一核对 | ✅ 无 .env/凭据/密钥/SSH 私钥/个人配置类文件；二进制仅 4 部国标 PDF（公开标准文本，见③） |
| ② 跟踪文本内容级扫描 | `tools/scan_sensitive.py tracked`——11 类模式：sk- 前缀密钥、GitHub token（ghp_/github_pat_）、私钥块、bearer、11 位手机号、18 位身份证、内网私网 IP、盘符用户路径（[盘符]:[/\]Users[/\]…）、个人路径词元（个人目录名/用户名片段）、键值形态密钥、邮箱；白名单=noreply 提交身份、git@github.com 公开 SSH URL、@pytest 代码标识符 | ✅ 修复后 **0 命中**（首轮发现 6 份 plan/HANDOFF-M*.md 用法行含本机绝对路径——个人路径泄露，见④） |
| ③ 二进制样例核对 | `git ls-files` 二进制类型识别 + sha256 对账 | ✅ 本仓无 docx/xlsx 等办公样例入仓；4 部 PDF sha256 与 `data/knowledge/raw/retrieval-log.md` 台账逐条一致 |
| ④ 历史重写（未推送 → 首推前完成，无需 force push） | 逐提交 `git grep` 定位 → 工作区改相对路径 → `git filter-branch --tree-filter` 全历史重写 → 清 refs/original/reflog → `git gc --prune=now` → `git fsck --unreachable` 空 | ✅ 8 个提交全部重写（泄露内容仅存在于 plan/HANDOFF-M*.md，无已删除文件漏网）；旧对象已物理清除 |

## 2. 提交元数据邮箱检查

- `git log --format="%ae %ce" --all` 唯一值 = `282769740+yuluo554@users.noreply.github.com`（D11 既定身份）✅

## 3. 历史终验三扫（阳性对照前置）

| 扫描 | 命令 | 结果 |
|---|---|---|
| 阳性对照（验证扫描命令本身） | `scan_sensitive.py selftest`：程序化合成假密钥/假手机号/假邮箱/假用户路径注入临时文件 | ✅ 五类全报出（首轮 selftest 抓出合成手机号仅 10 位未达 11 位正则的 bug——修正后全过，证明"对照也 0=方法坏了"的防线有效） |
| ① 内容 grep | `scan_sensitive.py tracked`（全部跟踪文本） | ✅ 0 |
| ② 历史补丁 | `scan_sensitive.py history`（`git log -p --all` 全文） | ✅ 0（重写后复验） |
| ③ 提交信息 | `scan_sensitive.py messages`（`git log --format=%B --all`） | ✅ 0 |

- MSYS 参数转写坑对冲（crash-loop-rescue skill 假结果陷阱节）：扫描一律用 Python 实现，不用 `/` 起始 grep 模式；逐对象 `git rev-list --all` + `git grep` 作权威判据。

## 4. 干净环境验证（发布门核心）

- 环境：工作区同级临时目录本地 clone（验证后已删）+ 全新 `py -m venv`（Python 3.8.8）。
- **README 快速开始逐字**：`python -m pip install -U pip`（首轮遇本机已知抖动 AssertionError，重试一次过 → pip 25.0.1）→ `python -m pip install -e .` 成功 → `flcheck --version` = 0.6.0 → `flcheck check examples/sample_label.txt --ruleset both` 退出码 0，`dual_diff.new_fails=[MAND-EXPIRY-01, SALT-NOTICE-01]` 与 README 示例一致。
- **extras**：`pip install -e ".[dev,web,report]"` 成功（fastapi 0.124.4 / uvicorn 0.33.0 / python-multipart 0.0.20 / python-docx 1.1.2 / pytest 8.3.5 / httpx 0.28.1）。
- **pytest 收集数对照**：干净环境 `--co` = **189** = dev 189 ✅（extras 第三形态"静默缺依赖整模块跳过"防线通过）。
- **全链 demo 全 0**：parse / gen（临时目录）/ bench parse / bench e2e / check --format table / check --report（39,100 字节 docx）/ web 线程起服探活（/api/health 200 + / 200 + 整页 0 http(s) 引用）。
- **加码**：干净 venv 分 3 批全量 pytest **69+68+52=189 全绿**（超出 DoD 最低要求，双环境证据）。

## 5. 建仓与推送（D12：token 无 workflow scope，走 SSH）

1. `gh repo create yuluo554/food-label-compliance-checker --public --source . --remote origin`（**不带 --push**）
2. `ssh -T git@github.com` → "Hi yuluo554! … successfully authenticated"
3. `git remote set-url origin git@github.com:yuluo554/food-label-compliance-checker.git`
4. `git push -u origin main` 一次成（含 .github/workflows/ci.yml，SSH 通道不受 workflow scope 限制）
5. git 链执行前 `pwd` + `git log --oneline -1` + `git remote -v` 三核对 ✅

## 6. tag / release / topics（经用户确认打包授权 2026-10-04）

- [x] 用户确认发布（AskUserQuestion 实录：确认发布 + D15 定为不投）
- [x] tag `v0.6.0` 打在含本文件的收尾回写提交上，随 release 推送
- [x] `gh release create v0.6.0 --notes-file <md>`（评测表数值 + 演示命令摘要 + extras 说明 + 免责声明）
- [x] topics：`gh repo edit --add-topic`（小写连字符）+ `gh api` 回读确认

## 7. 发布后复核（已回填 2026-10-04）

- **CI 事件实录**：首推即暴露 windows-latest 两作业 `UnicodeEncodeError`——`datagen/templates.py`/`injectors.py` 共 5 处 `strftime("%Y年…")`：Windows 的 strftime 按 locale（ANSI 代码页）编码格式串，CI 的 cp1252 编不了"年"；Ubuntu glibc 直通字节、本机 GBK 可编中文，两环境均测不出（"dev 绿 CI 挂"环境差异型；西文 Windows 用户跑 `flcheck gen` 同样会崩，修代码不修 CI 环境）。修复=e98d53c：`datagen.templates.fmt_cn_date` 手工格式化（输出逐字节一致，冻结集复现守门通过，DATAGEN_VERSION 不动）+ `tests/test_platform_guard.py` AST 双守门（src 禁 strftime 非 ASCII 格式串；src+tests 内建 open 强制 encoding=/二进制）。修复后 CI 四矩阵（ubuntu/windows × 3.8/3.11）全绿。
- **tag 迁移**：v0.6.0 初打在 CI 红的收尾提交上（发布后数分钟内、零消费者）→ 删 release+远端/本地 tag → 重打在含本节回填的收尾提交 → 重建 release（notes 增补 CI 全绿口径）。
- **GitHub 真实 clone 复核**：clone 修复提交 + 全新 venv → 收集数 **191**=dev、全量 **191 全绿**（69+70+52 分批）、bench parse/e2e 退出码 0、历史三扫全 0。
- **CI 对账**：push 4 次=run 4 次（修复前 main×2 与旧 tag 共 3 次失败=同一 strftime 根因、修复后 main 成功）；tag 重打后随 push/tag 各再触发 1 次，全绿——对账一致。
- 干净环境验证与发布后复核用的临时 clone/venv（工作区同级两处）及全部临时产物已删除。

## 8. D15 处置（plan/06 缓议项，经用户确认）

- **定为不投**：经查 2026 年"数据要素×"大赛（分赛报名 6 月–8 月初、总决赛 9 月）与第八届中国研究生人工智能创新大赛（报名 2026-05-22 至 08-25、作品提交至 09-01）窗口均已截止（查询日 2026-10-04）；用户决策不投赛事，本项闭环。
