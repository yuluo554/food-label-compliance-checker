"""flcheck 命令行入口。

退出码约定：0 = 审查/评测完成且达标（检出不合规项不算失败，结论看输出）；
1 = bench 评测跑通但未达门槛（F1 / 误报 / 检出率，见 plan/05 M4 DoD）；
2 = 用法/输入错误（含可选扩展依赖缺失，报错信息带安装提示）。
Windows 控制台建议 `py -X utf8 -m food_label_checker ...`（GBK 终端见 README 已知环境问题）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .bench.e2e_eval import DEFAULT_BENCH_DATA, evaluate_e2e
from .bench.parse_eval import PARSE_F1_GATE, evaluate_frozen, resolve_bench_data
from .datagen import generate_dataset, write_dataset
from .datagen.templates import resolve_categories
from .pipeline import parse_text, read_input, run_pipeline
from .rules.engine import resolve_ruleset_ids


def _setup_stdio() -> None:
    """控制台编码兜底：GBK 终端打印中文 JSON 不因个别字符崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flcheck",
        description="预包装食品标签合规智能审查系统（GB 7718/GB 28050 双标尺规则引擎）",
    )
    parser.add_argument("--version", action="version", version=f"flcheck {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="解析标签并按规则集审查（双标尺对照）")
    p_check.add_argument("input", help="标签文本文件路径（UTF-8）")
    p_check.add_argument(
        "--ruleset", default="both", help="规则集：2011 / 2025 / both（默认 both）"
    )
    p_check.add_argument(
        "--format", default="json", choices=["json", "table"],
        help="输出格式：json（默认，完整结果）/ table（人读摘要）",
    )
    p_check.add_argument(
        "--report", default=None, metavar="OUT.docx",
        help="生成 docx 审查报告到指定路径（需安装 report 扩展）",
    )
    p_check.add_argument(
        "--llm", action="store_true",
        help="启用 LLM 兜底（配置读 FOOD_LABEL_LLM_* 环境变量/.env，默认关闭；"
             "不可达/超时自动降级到规则通路）",
    )

    p_parse = sub.add_parser("parse", help="仅解析为标签参数卡 JSON")
    p_parse.add_argument("input", help="标签文本文件路径（UTF-8）")

    p_gen = sub.add_parser("gen", help="合成标签生成器：固定 seed 生成带真值数据集")
    p_gen.add_argument("--seed", type=int, default=42, help="随机种子（默认 42，位级可复现）")
    p_gen.add_argument("--n", type=int, default=12, help="样本总数（默认 12：4 品类各 1 干净版 + V1–V8 各 1）")
    p_gen.add_argument(
        "--categories",
        default=None,
        help="品类列表，逗号分隔：乳制品/饮料/烘焙/调味品 或 dairy/beverage/bakery/condiment（默认全部）",
    )
    p_gen.add_argument("--out", default="data/generated", help="输出根目录（默认 data/generated）")
    p_gen.add_argument(
        "--force", action="store_true", help="目标目录已存在时删除重生成（缺省报错退出，保护已冻结数据）"
    )

    p_bench = sub.add_parser(
        "bench",
        help="内置基准评测（零 API 依赖；退出码 0 达标 / 1 未达标）",
    )
    bench_sub = p_bench.add_subparsers(dest="bench_kind")
    bp_parse = bench_sub.add_parser(
        "parse", help=f"解析 F1 基准（门槛 F1 ≥ {PARSE_F1_GATE}）"
    )
    bp_parse.add_argument(
        "--data", default=DEFAULT_BENCH_DATA,
        help=f"数据集目录（含 truth.json，默认 {DEFAULT_BENCH_DATA}）",
    )
    bp_parse.add_argument(
        "--min-f1", type=float, default=PARSE_F1_GATE, help="F1 合格线（默认 0.95）"
    )
    bp_e2e = bench_sub.add_parser(
        "e2e", help="端到端对账基准（合格线：误报 0 / 检出率 1.0 / dual_diff 零违例）"
    )
    bp_e2e.add_argument(
        "--data", default=DEFAULT_BENCH_DATA,
        help="数据集目录（含 truth.json，默认 data/generated/frozen/seed-2026-n12）",
    )

    p_web = sub.add_parser("web", help="启动 Web 面板（FastAPI，0 外链内联单页）")
    p_web.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    p_web.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    return parser


def _finding_lines(finding: dict) -> list:
    """单条结论的人读展示行（table 输出用）。"""
    lines = []
    marker = "✗ 不合规" if finding["level"] == "不合规" else "? 待人工确认"
    lines.append(f"  {marker} [{finding['rule_id']}] {finding['message']}")
    basis = finding.get("basis") or {}
    if basis.get("standard") or basis.get("clause"):
        lines.append(f"      依据：{basis.get('standard', '')} {basis.get('clause', '')}".rstrip())
    if finding.get("advice"):
        lines.append(f"      建议：{finding['advice']}")
    evidence = finding.get("evidence") or {}
    quote = evidence.get("quote") or ""
    if quote:
        shown = quote[:60] + ("…" if len(quote) > 60 else "")
        lines.append(f"      证据（{evidence.get('region', '')}）：{shown}")
    return lines


def _print_check_table(result: dict) -> None:
    """check --format table：人读摘要输出（JSON 仍是默认与机读口径）。"""
    card = result["card"]
    name_field = card.get("fields", {}).get("food_name") or {}
    print("[flcheck] 食品标签合规审查")
    print(f"  食品名称：{name_field.get('value', '（未识别）')}")
    print(f"  规则集：{' + '.join(result['ruleset_ids'])}    引擎版本：v{result['engine_version']}")
    for rid, res in result["results"].items():
        stats = res["stats"]
        print()
        print(
            f"■ {rid}：检查 {stats.get('checked', 0)} 项｜"
            f"合规 {stats.get('pass', 0)}｜不合规 {stats.get('fail', 0)}｜"
            f"待人工 {stats.get('manual', 0)}"
        )
        for finding in res["findings"]:
            if finding["level"] == "合规":
                continue
            for line in _finding_lines(finding):
                print(line)
    if "dual_diff" in result:
        dd = result["dual_diff"]
        print()
        print(
            f"■ 双标尺对照（{dd['baseline']} → {dd['target']}）："
            f"新增不合规 {dd['new_fails']}｜消除 {dd['resolved_fails']}"
        )
    fb = result.get("fallback") or {}
    fb_line = f"■ LLM 兜底：{fb.get('status', 'off')}"
    if fb.get("filled_keys"):
        fb_line += f"（填充：{', '.join(fb['filled_keys'])}）"
    print(fb_line)


def main(argv=None) -> int:
    _setup_stdio()
    parser = build_parser()
    ns = parser.parse_args(argv)

    if ns.command is None:
        parser.print_help()
        return 2

    try:
        if ns.command == "check":
            llm_config = None
            if ns.llm:
                from .llm.config import from_env as llm_from_env

                llm_config = llm_from_env()
                llm_config.enabled = True  # --llm 为显式开启开关
            result = run_pipeline(
                input_path=ns.input,
                ruleset_ids=resolve_ruleset_ids(ns.ruleset),
                llm_config=llm_config,
            )
            for warning in result.get("warnings", []):
                print(f"[flcheck] 警告：{warning}", file=sys.stderr)
            if ns.format == "table":
                _print_check_table(result)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            if ns.report:
                from .report.docx_report import generate_report

                out_path = generate_report(result, ns.report)
                print(f"[flcheck] docx 报告已生成：{Path(out_path).as_posix()}", file=sys.stderr)
            return 0
        if ns.command == "parse":
            text = read_input(ns.input)
            print(json.dumps(parse_text(text), ensure_ascii=False, indent=2))
            return 0
        if ns.command == "gen":
            if ns.n < 1:
                raise ValueError(f"--n 至少为 1，收到 {ns.n}")
            categories = resolve_categories(ns.categories)
            out_root = Path(ns.out)
            target = out_root / f"seed-{ns.seed}-n{ns.n}"
            if ns.force and target.exists():
                shutil.rmtree(target)
            truth, texts = generate_dataset(ns.seed, ns.n, categories)
            written = write_dataset(truth, texts, out_root)
            clean = sum(1 for s in truth["samples"] if s["clean_baseline"])
            print(
                f"[flcheck] 生成完成：{written.as_posix()}（样本 {len(texts)} = "
                f"干净 {clean} + 注入 {len(texts) - clean}；真值 truth.json；"
                "位级复现校验见 manifest.json 与 tests/test_datagen_repro.py）"
            )
            return 0
        if ns.command == "bench":
            if ns.bench_kind is None:
                print(
                    "[flcheck] bench 需要子命令：parse（解析 F1）/ e2e（端到端对账），"
                    "详见 `flcheck bench --help`。",
                    file=sys.stderr,
                )
                return 2
            if ns.bench_kind == "parse":
                data_dir = resolve_bench_data(ns.data)
                metrics, issues = evaluate_frozen(data_dir=data_dir)
                gate = {"metric": "f1", "threshold": ns.min_f1,
                        "passed": metrics["f1"] >= ns.min_f1}
                payload = {"bench": "parse", "data": data_dir.as_posix(),
                           "metrics": metrics, "gate": gate,
                           "issues": issues[:50] + (["……（截断）"] if len(issues) > 50 else [])}
            else:  # e2e
                data_dir = resolve_bench_data(ns.data)
                metrics, issues = evaluate_e2e(data_dir=data_dir)
                gate = {
                    "thresholds": {"false_positives": 0, "detection_rate": 1.0,
                                   "dual_diff_violations": 0},
                    "passed": (
                        metrics["false_positives"] == 0
                        and metrics["detection_rate"] == 1.0
                        and not metrics["dual_diff_violations"]
                    ),
                }
                payload = {"bench": "e2e", "data": Path(ns.data).as_posix(),
                           "metrics": metrics, "gate": gate,
                           "issues": issues[:50] + (["……（截断）"] if len(issues) > 50 else [])}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0 if gate["passed"] else 1
        if ns.command == "web":
            from .webapp import create_app

            try:
                import uvicorn  # noqa: F401
            except ImportError:
                print(
                    "Web 面板需要安装 web 扩展：pip install 'food-label-compliance-checker[web]'",
                    file=sys.stderr,
                )
                return 2
            uvicorn.run(create_app(), host=ns.host, port=ns.port)
            return 0
    except FileNotFoundError as exc:
        print(f"[flcheck] {exc}", file=sys.stderr)
        return 2
    except FileExistsError as exc:
        print(f"[flcheck] {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        # 可选扩展（report/web/llm）依赖缺失：打印安装提示，优雅退出不崩溃。
        print(f"[flcheck] {exc}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[flcheck] {exc}", file=sys.stderr)
        return 2

    print(
        f"[flcheck] 子命令『{ns.command}』尚未实现：实现里程碑见 plan/05-数据计划与里程碑.md。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
