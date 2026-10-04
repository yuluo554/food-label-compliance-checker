# -*- coding: utf-8 -*-
"""平台兼容守门（CI Windows cp1252 实录回归）。

背景：GitHub windows-latest 的 ANSI 代码页是 cp1252，本机是 GBK——datetime.strftime
在 Windows 上按 locale 编码格式串，非 ASCII 字面量（如 %Y年%m月%d日 的"年"）在
cp1252 直接 UnicodeEncodeError（Ubuntu glibc 直通字节、本机 GBK 可编中文，两处都测
不出来，只有 CI Windows 崩——"dev 绿 + CI 挂"环境差异型，plan/RELEASE-M6.md §7 实录）。

静态 AST 审计两条线：
1. src/**.py 不得出现 strftime/time.strftime 携带非 ASCII 格式串（统一走
   datagen.templates.fmt_cn_date 手工格式化）；
2. src+tests 的内建 open() 必须显式 encoding= 或二进制模式（UTF-8 语料在 cp1252
   下按 locale 读会 UnicodeDecodeError/Mojibake）。
"""
import ast
import os

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def py_files(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def test_no_nonascii_strftime_in_src():
    bad = []
    for path in py_files(SRC):
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for call in _calls(tree):
            func = call.func
            name = getattr(func, "attr", None) or (
                getattr(func, "id", "") if isinstance(func, ast.Name) else "")
            if name != "strftime" or not call.args:
                continue
            arg = call.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if any(ord(ch) > 127 for ch in arg.value):
                    rel = os.path.relpath(path, ROOT)
                    bad.append("%s:%d %r" % (rel, call.lineno, arg.value))
    assert not bad, "strftime 非 ASCII 格式串（cp1252 崩溃隐患，改用 fmt_cn_date）：%s" % bad


def test_open_calls_have_explicit_encoding_or_binary():
    bad = []
    for base in (SRC, os.path.join(ROOT, "tests")):
        for path in py_files(base):
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for call in _calls(tree):
                func = call.func
                if not (isinstance(func, ast.Name) and func.id == "open"):
                    continue
                has_encoding = any(kw.arg == "encoding" for kw in call.keywords)
                binary = False
                if call.args:
                    mode_arg = call.args[1] if len(call.args) > 1 else None
                    if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                        binary = "b" in mode_arg.value
                    for kw in call.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            binary = binary or ("b" in (kw.value.value or ""))
                if not (has_encoding or binary):
                    rel = os.path.relpath(path, ROOT)
                    bad.append("%s:%d" % (rel, call.lineno))
    assert not bad, "open() 缺显式 encoding/二进制模式（cp1252 读 UTF-8 语料隐患）：%s" % bad
