"""flcheck 命令行入口。

退出码约定：0 = 审查完成（含检出不合规项，结论看输出）；2 = 用法/输入错误。
Windows 控制台建议 `py -X utf8 -m food_label_checker ...`（GBK 终端见 README 已知环境问题）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .pipeline import check_text, parse_text
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
        "--format", default="json", choices=["json"], help="输出格式（table 随 M5 增加）"
    )

    p_parse = sub.add_parser("parse", help="仅解析为标签参数卡 JSON")
    p_parse.add_argument("input", help="标签文本文件路径（UTF-8）")

    sub.add_parser("gen", help="合成标签生成器（M1 实现）")
    sub.add_parser("bench", help="内置基准评测（M4 实现）")
    sub.add_parser("web", help="启动 Web 面板（M5 实现）")
    return parser


def _read_input(raw: str) -> str:
    path = Path(raw)
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在：{path}")
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"输入文件需为 UTF-8 编码：{exc}") from exc


def main(argv=None) -> int:
    _setup_stdio()
    parser = build_parser()
    ns = parser.parse_args(argv)

    if ns.command is None:
        parser.print_help()
        return 2

    try:
        if ns.command == "check":
            text = _read_input(ns.input)
            result = check_text(text, resolve_ruleset_ids(ns.ruleset))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if ns.command == "parse":
            text = _read_input(ns.input)
            print(json.dumps(parse_text(text), ensure_ascii=False, indent=2))
            return 0
    except FileNotFoundError as exc:
        print(f"[flcheck] {exc}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[flcheck] {exc}", file=sys.stderr)
        return 2

    print(
        f"[flcheck] 子命令『{ns.command}』尚未实现：当前为 M0 骨架阶段，"
        "实现里程碑见 plan/05-数据计划与里程碑.md。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
