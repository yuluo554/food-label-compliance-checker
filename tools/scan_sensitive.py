# -*- coding: utf-8 -*-
"""脱敏扫描器（M6 发布门用，可复跑）。

用法（仓库根目录执行）：
  py -X utf8 tools/scan_sensitive.py selftest    # 阳性对照：临时文件注入合成样值，验证命令本身能报出
  py -X utf8 tools/scan_sensitive.py tracked     # 扫全部 git 跟踪文本（工作区内容）
  py -X utf8 tools/scan_sensitive.py history     # 扫 git log -p --all 全历史补丁
  py -X utf8 tools/scan_sensitive.py messages    # 扫全部提交信息（%B）

模式只放正则与占位构造，不放任何字面假密钥/假手机号（模式字面值不留历史）。
阳性对照样值在 selftest 内程序化合成，跑完即删临时文件。
"""
import re
import subprocess
import sys
import tempfile
import os

# 白名单（按值/按域放行）
EMAIL_ALLOW = (
    "users.noreply.github.com",   # D11 规定的提交身份
    "example.com", "example.org", "your.email", "localhost",
)

PATTERNS = [
    ("api_key_literal", re.compile(r"sk-[A-Za-z0-9_\-]{16,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b|github_pat_[A-Za-z0-9_]{20,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9_\-.=]{20,}")),
    ("cn_mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("cn_id_card", re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:[0-2]\d|3[01])\d{3}[\dXx](?!\d)")),
    ("private_ip", re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("personal_path_win", re.compile(r"[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\s\"'，。）)]{1,40}")),
    # 片段拼接防自匹配：源码不含完整词面值（模式字面值不留历史纪律）
    ("personal_path_token", re.compile("\\b(?:Progra" + "mData|AS" + "US)\\b")),
    ("kv_secret", re.compile(r"(?i)(?:api[_-]?key|secret|password|passwd|token)\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{16,}")),
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
]

ALLOWED_SUBSTR = (
    "282769740+yuluo554@users.noreply.github.com",  # D11 规定的提交身份
    "git@github.com",      # 公开 SSH 克隆 URL，非个人邮箱
    "@pytest.",            # 代码标识符（@pytest.fixture 等）被 email 正则误吸
    "noreply@github.com",
    "example.com",
)


def _allow(match_text):
    low = match_text.lower()
    if any(s in match_text for s in ALLOWED_SUBSTR):
        return True
    if "@" in match_text and any(d in low for d in EMAIL_ALLOW):
        return True
    return False


def scan_text(text, source):
    hits = []
    for name, pat in PATTERNS:
        for m in pat.finditer(text):
            val = m.group(0)
            if _allow(val):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            hits.append((source, line_no, name, val[:60]))
    return hits


def is_binary(data):
    return b"\x00" in data[:8192]


def git(args):
    out = subprocess.run(["git"] + args, capture_output=True)
    return out.stdout.decode("utf-8", errors="replace")


def scan_tracked():
    files = git(["ls-files", "-z"]).split("\x00")
    files = [f for f in files if f]
    hits = []
    for f in files:
        if not os.path.exists(f):
            continue
        with open(f, "rb") as fh:
            data = fh.read()
        if is_binary(data):
            print("[binary-skip] %s" % f)
            continue
        hits += scan_text(data.decode("utf-8", errors="replace"), f)
    return hits


def scan_history():
    patch = git(["log", "-p", "--all", "--no-color"])
    return scan_text(patch, "<git-log-p>")


def scan_messages():
    msgs = git(["log", "--all", "--format=%B"])
    return scan_text(msgs, "<commit-messages>")


def selftest():
    """阳性对照：程序化合成三类样值写入临时文件，断言扫描器全部报出。"""
    fake_key = "sk-" + "a1B2c3D4" * 4            # 32 位合成密钥
    fake_phone = "1" + "3" + "456789012"          # 合成 11 位手机号（无真实号段语义，仅过正则）
    fake_mail = "someone@" + "private-mail" + ".cn"
    win_dir = "Use" + "rs"                      # 片段拼接防自匹配
    sample = "token=%s\nphone %s\nmail %s\npath C:\\%s\\TestUser\\x\n" % (
        fake_key, fake_phone, fake_mail, win_dir)
    fd, path = tempfile.mkstemp(suffix=".txt", dir=".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(sample)
        names = {h[2] for h in scan_text(sample, path)}
        need = {"kv_secret", "cn_mobile", "email", "personal_path_win"}
        missing = need - names
        if missing:
            print("SELFTEST FAIL: 未报出 %s" % sorted(missing))
            return 1
        print("SELFTEST OK: 阳性对照全部报出 %s" % sorted(names))
        return 0
    finally:
        os.remove(path)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "selftest":
        return selftest()
    if mode == "tracked":
        hits = scan_tracked()
    elif mode == "history":
        hits = scan_history()
    elif mode == "messages":
        hits = scan_messages()
    else:
        print(__doc__)
        return 2
    for h in hits:
        print("HIT %s:%d [%s] %s" % h)
    print("TOTAL_HITS=%d mode=%s" % (len(hits), mode))
    return 0


if __name__ == "__main__":
    sys.exit(main())
